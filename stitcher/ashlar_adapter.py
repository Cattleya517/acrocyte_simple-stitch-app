# Based on the file contents, here's a summary of the classes defined:

# **Core Classes:**
# - `FileSeriesHelper2` - Parses image filenames using regex patterns and creates BioformatsReader2 objects for each (series, channel) pair
# - `FileSeriesMetadata2` - Extends `reg.PlateMetadata` to handle metadata for file series, providing properties like pixel size, channels, and tile information
# - `FileSeriesReader2` - Extends `reg.PlateReader` to read images from file series using the metadata and helper classes

# **Writer Classes:**
# - `WriterHelper` - Static utility class with methods for assembling images to zarr arrays and creating downscaled layers
# - `ZarrWriter` - Exports mosaics to standard Zarr format
# - `SpatialDataWriter` - Exports mosaics to SpatialData zarr format with support for scale factors and channel metadata
# - `OMEZarrWriter` - Exports mosaics to OME-Zarr format with pyramid layers and channel rendering settings

# **Enhanced BioFormats Classes:**
# - `BioformatsMetadata2` - Extends `reg.BioformatsMetadata` to add channel information (name, color) and OME-XML metadata properties
# - `BioformatsReader2` - Extends `reg.BioformatsReader` using the enhanced metadata class

# **Utility Classes:**
# - `EstimateIllumination` - Uses BaSiC algorithm to estimate and save flatfield/darkfield profiles for illumination correction

# The classes are designed to work with Molecular Devices (MD) image filename patterns and provide various export formats for microscopy image mosaics.


from logging import root
import re
from xml import dom
from tqdm import tqdm
import ashlar.reg as reg
import numpy as np
import pandas as pd
import tifffile
import xml.etree.ElementTree as ET
from .metamorphtiff import MD_PATTERN, MetaMorphTIFFHelper

# Heavy optional imports — only needed by writer classes and EstimateIllumination,
# not by FileSeriesReader2/FileSeriesMetadata2. Deferred to avoid import errors
# when these packages have dependency conflicts.
def _import_writers():
    import zarr
    import dask.array as da
    from ome_zarr.scale import Scaler
    from ome_zarr.writer import write_image
    try:
        from ome_zarr.writer import add_metadata
    except ImportError:
        def add_metadata(group, metadata):
            group.attrs.update(metadata)
    import spatialdata as sd
    return zarr, da, Scaler, write_image, add_metadata, sd

def _import_basicpy():
    from basicpy import BaSiC
    return BaSiC


# -------------------------------------------------------------------------------------- 
# 1. group 'series' and 'channel' must be integers
# 2. each image file is -
#    a. indexed by (series, channel)
#    b. handled by a BioformatsReader2 object
# 3. self.servers[(series, channel)] = BioformatsReader2 object
#    a. contain all the information we need
#    b. can implement the abstract methods defined in reg.Metadata
# 4. only support plate=None and well=None right now
#    a. the abstract methods defined in reg.PlateMetadata are not implemented
class FileSeriesMetadata2(reg.PlateMetadata):
    def __init__(self, path, pattern=MD_PATTERN):
        super(FileSeriesMetadata2, self).__init__()
        helper = MetaMorphTIFFHelper(path, pattern)
        self.path    = path
        self.pattern = pattern
        self.df      = helper.to_dataframe()
        self.idx     = pd.IndexSlice
        # Normalize tile positions to start from (0,0) to avoid
        # floating-point precision issues in ashlar's alignment.
        self._normalize_positions()
#        helper.check_integrity(self.database)

    @property
    def num_plates(self):
        return len(self.df.loc[self.idx[:, 0, 0], 'plate_name'])

    @property
    def num_wells(self):
        return [
            len(self.df.loc[self.idx[p, :, 0], 'well_name'])
            for p in range(self.num_plates)
        ]
    
    def plate_name(self, plate_idx):
        return self.df.loc[self.idx[plate_idx, 0, 0], 'plate_name']
    
    def well_name(self, plate_idx, well_idx):
        return self.df.loc[self.idx[plate_idx, well_idx, 0], 'well_name']    

    @property
    def well_naming(self):
        return [['letter', 'number']] * self.num_plates

    @property
    def plate_well_series(self):
        if not hasattr(self, '_plate_well_series'):
            self._plate_well_series = [
                [
                    [self.df.index.get_loc(i) for i in self.df.loc[self.idx[p, w, :], :].index]
                    for w in range(self.num_wells[p])
                ]
                for p in range(self.num_plates)
            ]
        return self._plate_well_series

    @property
    def _num_images(self):
        return len(self.df)   # all plates and wells

    @property
    def num_channels(self):
        return len(self.df.iloc[0]['file_path'])  # use image 0
    
    @property
    def pixel_size(self):
        return self.df.iloc[0]['pixel_size']      # use image 0
    @property
    def pixel_dtype(self):
        return self.df.iloc[0]['pixel_dtype']     # use image 0
    
    def _normalize_positions(self):
        positions = np.vstack(self.df['tile_position'].values)
        origin = positions.min(axis=0)
        self.df['tile_position'] = [pos - origin for pos in self.df['tile_position']]

    def tile_position(self, image_idx):
        return self.df.iloc[image_idx]['tile_position']
    
    def tile_size(self, image_idx):
        return self.df.iloc[image_idx]['tile_size']
    
    def file_path(self, series_idx, channel_idx):
        image_idx = self.active_series[series_idx]
        return self.df.iloc[image_idx]['file_path'][channel_idx]

    @property
    # MetaMorphTIFF does not have channel color information
    def channels(self):
        if not hasattr(self, '_channels'):
            channel_name = self.df.iloc[0]['channel_name']
            self._channels = []
            for i, name in enumerate(channel_name):
                self._channels.append({
                    'name':  name or str(i),
                    'color': (
                        self._name2color(name) or 
                        self._CHANNEL[i % len(self._CHANNEL)]['color']
                    )
                })
        return self._channels

    # utilities to handle channel information
    # 1. adopted from https://github.com/corallin290/acrocyte/blob/trunk/lib/actutil.py#L1-L15
    # 2. for convenience, not for efficiency
    _CHANNEL = [
        {'color': "0000FF", 'title': 'DAPI',     'name': ['B', 'DAPI', 'HOECHST', 'W0'] },          # Blue
        {'color': "FF0000", 'title': 'EpCam',    'name': ['R', 'CY5', 'EPCAM'] },                   # Red
        {'color': "00FF00", 'title': 'CD45',     'name': ['G', 'FITC', 'CD45'] },                   # Green
        {'color': "FFFF00", 'title': 'HER2',     'name': ['Y', 'TRITC', 'HER2', 'PDL1', 'PD-L1'] }, # Yellow
        {'color': "F75C2F", 'title': 'TEXASRED', 'name': ['T', 'TEXASRED'] },                       # Orange
        {'color': "FFFFFF", 'title': 'TL25',     'name': ['K', "TL25"] },                           # White
        {'color': "FFFFFF", 'title': 'Tx',       'name': ['TRANSMITTEDLIGHT', 'TX'] },              # White
    ]

    def _name2color(self, name):
        for prop in self._CHANNEL:
            if name.replace(" ", "").upper() in prop['name']:
                return prop['color']
        return None   
    
    def _name2title(self, name):
        for prop in self._CHANNEL:
            if name.replace(" ", "").upper() in prop['name']:
                return prop['title']
        return None



# --------------------------------------------------------------------------------------
# image servers are placed under metadata because:
# 1. I want FileSeriesMetadata2 can be used independently
# 2. make FileSeriesReader2 has similar structure as BioformatsReader2
class FileSeriesReader2(reg.PlateReader):
    def __init__(self, path, plate=None, well=None, pattern=MD_PATTERN):
        self.path     = path
        self.pattern  = pattern
        self.metadata = FileSeriesMetadata2(self.path, self.pattern)
        self.metadata.set_active_plate_well(plate, well)

    # both series and c are integers
    def read(self, series_idx, channel_idx):
        file_path = self.metadata.file_path(series_idx, channel_idx)
        return tifffile.memmap(file_path)
    
    # # both series and c are integers
    # def to_dask_array(self, series, c, chunks=(512, 512)):
    #     server = self.servers[(series, c)]
    #     return server.to_dask_array(0, 0, chunks)   # every image file has only one image plane



# --------------------------------------------------------------------------------------
# helper functions for writers
class WriterHelper:
    # assemble the full image into a zarr array channel by channel
    # 1. require sufficient memory to hold a single channel image
    # 2. the aligner requires all DAPI tiles to be loaded into memory
    # 3. assemble_channel(c, image[c, :, :]) won't work because
    #    a. image[c, :, :] is a np.array, not a zarr array
    #    b. any modifications on it won't change the original zarr array on disk
    @staticmethod
    def assemble_image_to_zarr(mosaic, image, verbose=False):
        for c in mosaic.channels:
            if verbose:
                print(f"assembling channel {c+1}/{len(mosaic.channels)}")
            image[c, :, :] = mosaic.assemble_channel(c)

    # generate downscaled layers from the original image layer
    # 1. assume layers are ordered by size (largest first)
    # 2. use da.coarsen(np.mean, ...) to generate the downscaled layers
    @staticmethod
    def write_downscaled_layers(layers, verbose=False):
        x           = da.from_zarr(layers[0])   # the original image
        trim_excess = True                      # the original image is trimmed to be divisible
        for layer in layers[1:]:
            axes = {axis: int(up/down) for axis, (up, down) in enumerate(zip(x.shape, layer.shape))}
            scaled = da.coarsen(np.mean, x, axes=axes, trim_excess=trim_excess)
            assert scaled.shape == layer.shape, f"downscaled shape {scaled.shape} != target shape {layer.shape}"
            scaled.to_zarr(layer)               # only change the values (zarr structre stays the same)



# --------------------------------------------------------------------------------------
# export the mosaic in Zarr format
# 1. zarr.open(...)               to create an empty zarr array
# 2. assemble_image_to_zarr(...)  to fill in the data
# 3. zarr_version=2 by default for compatibility
class ZarrWriter:
    def __init__(self, mosaic, path, chunks=(1, 1024, 1024), zarr_version=3, verbose=False):
        self.mosaic       = mosaic
        self.metadata     = mosaic.aligner.metadata
        self.path         = path
        self.shape        = (len(mosaic.channels),) + mosaic.shape
        self.chunks       = chunks
        self.dtype        = mosaic.dtype
        self.zarr_version = zarr_version
        self.verbose      = verbose

    def create_an_empty_zarr_array(self):
        z = zarr.open(
            self.path,
            mode="w",
            shape=self.shape,
            chunks=self.chunks,
            dtype=self.dtype,
            zarr_version=self.zarr_version,
        )

        return z
    
    def run(self):
        z = self.create_an_empty_zarr_array()
        WriterHelper.assemble_image_to_zarr(self.mosaic, z, self.verbose)



# --------------------------------------------------------------------------------------
# export the mosaic in SpatialData zarr format
# 0. spatialdata does nto have api to specify channel colors 
# 1. sd.SpatialData()                     to create an empty SpatialData object
# 2. sd.models.Image2DModel.parse(...)    to create an empty image layer within it
# 3. sdata.write(...) & sd.read_zarr(...) to make the object backed by a zarr store
# 4. assemble_image_to_zarr(...)  to fill in the data for the base layer
# 5. write_downscaled_layers(...) to generate its downscaled layers
# 6. scale_factors=[2, 2] - 2 downscaled layers (2x and 4x)
class SpatialDataWriter:
    def __init__(self, mosaic, path, image_layer="raw_image", chunks=(1, 1024, 1024), scale_factors=None, verbose=False):
        self.mosaic        = mosaic
        self.metadata      = mosaic.aligner.metadata
        self.path          = path
        self.image_layer   = image_layer
        self.shape         = (len(mosaic.channels),) + mosaic.shape
        self.chunks        = chunks
        self.dtype         = mosaic.dtype
        self.scale_factors = scale_factors
        self.verbose       = verbose

    def create_an_empty_spatialdata_zarr(self, with_channels=False):
        # create an empty SpatialData object
        sdata = sd.SpatialData()

        # compose c_coords
        if with_channels:
            c_coords = [c['name'] for c in self.metadata.channels]
            c_coords = c_coords if all(c_coords) else None

        # create an empty image layer (initialized to zeros)
        image = da.empty(shape=self.shape, chunks=self.chunks, dtype=self.dtype)
        sdata[self.image_layer] = sd.models.Image2DModel.parse(
            data=image,
            dims=["c", "y", "x"],
            c_coords=c_coords if with_channels else None,
            scale_factors=self.scale_factors,
        )

        # make 'sdata' backed by local zarr store 'path'
        sdata.write(self.path, overwrite=True)
        sdata = sd.read_zarr(self.path)

        return sdata

    def run(self, with_channels=False):
        sdata = self.create_an_empty_spatialdata_zarr(with_channels=with_channels)
        root  = zarr.open(sdata.path / "images" / self.image_layer)

        # retrieve the pyramid layers by size (largest first)
        layers = [layer for _, layer in root.members()]
        layers = sorted(layers, key=lambda x: x.size, reverse=True)

        WriterHelper.assemble_image_to_zarr(self.mosaic, layers[0], self.verbose)
        WriterHelper.write_downscaled_layers(layers, self.verbose)



# --------------------------------------------------------------------------------------
# export the mosaic in OME-Zarr format
# 0. follow the instruction of https://ome-zarr.readthedocs.io/en/stable/python.html
# 1. zarr.open(...)   to create the OME-Zarr top-level group
# 2. write_image(...) to create an empty OME-Zarr image pyramid within it
# 3. assemble_image_to_zarr(...)  to fill in the data for the base layer
# 4. write_downscaled_layers(...) to generate its downscaled layers
# 5. zarr_version=2 by default for compatibility
class OMEZarrWriter:
    def __init__(self, mosaic, path, chunks=(1, 1024, 1024), downscale=None, zarr_version=3, verbose=False):
        self.mosaic       = mosaic
        self.metadata     = mosaic.aligner.metadata
        self.path         = path
        self.shape        = (len(mosaic.channels),) + mosaic.shape
        self.chunks       = chunks
        self.dtype        = mosaic.dtype
        self.downscale    = downscale
        self.zarr_version = zarr_version
        self.verbose      = verbose

    def create_an_empty_ome_zarr(self, with_channels=False):
        # ome-zarr top-level root group
        root = zarr.open(
            self.path,
            mode="w",
            zarr_version=self.zarr_version,
        )

        # create an empty OME-Zarr image pyramid
        image  = da.empty(shape=self.shape, chunks=self.chunks, dtype=self.dtype)
        scaler = Scaler(downscale=self.downscale) if self.downscale else None
        write_image(
            image=image,
            group=root,
            scaler=scaler,
            axes=["c", "y", "x"],
        )

        # rendering settings
        if with_channels:
            add_metadata(root, {"omero": {
                "channels": self._render_channels()
            }})

        return root

    def run(self, with_channels=False):
        root = self.create_an_empty_ome_zarr(with_channels=with_channels)

        # retrieve the pyramid layers by size (largest first)
        layers = [layer for _, layer in root.members()]
        layers = sorted(layers, key=lambda x: x.size, reverse=True)

        WriterHelper.assemble_image_to_zarr(self.mosaic, layers[0], self.verbose)
        WriterHelper.write_downscaled_layers(layers, self.verbose)

    # utilities to handle channel information
    # 1. adopted from https://github.com/corallin290/acrocyte/blob/trunk/lib/actutil.py#L1-L15
    # 2. for convenience, not for efficiency
    _CHANNEL = [
        {'color': "0000FF", 'name': ['B', 'DAPI', 'HOECHST', 'W0'] },          # Blue
        {'color': "FF0000", 'name': ['R', 'CY5', 'EPCAM'] },                   # Red
        {'color': "00FF00", 'name': ['G', 'FITC', 'CD45'] },                   # Green
        {'color': "FFFF00", 'name': ['Y', 'TRITC', 'HER2', 'PDL1', 'PD-L1'] }, # Yellow
        {'color': "F75C2F", 'name': ['T', 'TEXASRED'] },                       # Orange
        {'color': "FFFFFF", 'name': ['K', "TL25"] },                           # White
    ]

    def _name2color(self, name):
        for prop in self._CHANNEL:
            if name.replace(" ", "").upper() in prop['name']:
                return prop['color']
        return None   

    def _render_channels(self):
        channels = []
        for i, channel in enumerate(self.metadata.channels):
            name  = channel['name'] or str(i)
            color = (
                channel['color'] or 
                self._name2color(name) or 
                self._CHANNEL[i % len(self._CHANNEL)]['color']
            )
            channels.append({
               "label":   name,
                "color":  color,
                "active": True,
            })
        return channels



# --------------------------------------------------------------------------------------
# use BaSiC to estimate & save flatfield and darkfield profiles
# 0. check out https://github.com/peng-lab/BaSiCPy to learn more about BaSiC
# 1. flatfield and darkfield are saved as TIFF files for ashlar integration
# 2. require sufficient memory to hold all images for each channel
# 3. input:
#    a. reader   - a reg.PlateReader object
#    b. ffp_path - output flatfield TIFF file path
#    c. dfp_path - output darkfield TIFF file path
# 4. output:
#    a. self.flatfield - estimated flatfield profile (numpy array)
#    b. self.darkfield - estimated darkfield profile (numpy array)
class EstimateIllumination:
    def __init__(self, reader, ffp_path, dfp_path, overwrite=True):
        self.reader    = reader
        self.ffp_path  = ffp_path
        self.dfp_path  = dfp_path
        self.flatfield = None
        self.darkfield = None
        self.baseline  = None
        if (ffp_path != None) and (dfp_path != None):
            self._load_or_run(overwrite)

    def _load_or_run(self, overwrite):
        if overwrite or (not self.ffp_path.exists()) or (not self.dfp_path.exists()):
            self._run()
        else:
            self.flatfield = tifffile.imread(self.ffp_path)
            self.darkfield = tifffile.imread(self.dfp_path)

    def _run(self):
        # compute flatfield & darkfield
        models = []
        nimages   = self.reader.metadata.num_images
        nchannels = self.reader.metadata.num_channels
        for c in tqdm(range(nchannels), desc="Fitting BaSiC models"):
            # construct the sample image set for model fitting
            image_list = [self.reader.read(s, c) for s in range(nimages)]
            images = np.stack(image_list, axis=0)

            # model fitting
            model = BaSiC(get_darkfield=True, smoothness_flatfield=1)   # create a BaSiC object
            model.fit(images)                                           # fit the model
            models.append(model)                                        # store the fitted model

        # extract flatfield & darkfield
        self.flatfield = np.stack([model.flatfield for model in models], axis=0)
        self.darkfield = np.stack([model.darkfield for model in models], axis=0)
        self.baseline  = np.stack([model.baseline for model in models], axis=0)

        # save flatfield and darkfield as TIFF files (for ashlar integration)
        tifffile.imwrite(self.ffp_path, np.squeeze(self.flatfield))
        tifffile.imwrite(self.dfp_path, np.squeeze(self.darkfield))
        
    # more memory-efficient version with image resizing (not quite sure it is worth it)
    # def _run(self):
    #     from basicpy import BaSiC
    #     from skimage.transform import resize as skimage_size

    #     # compute flatfield & darkfield
    #     models = []
    #     nimages     = self.reader.metadata.num_images
    #     nchannels   = self.reader.metadata.num_channels
    #     image_shape = tuple(self.reader.metadata.size)
    #     for c in tqdm(range(nchannels), desc="Fitting BaSiC models"):
    #         # create a BaSiC object
    #         model = BaSiC(get_darkfield=True, smoothness_flatfield=1)
    
    #         # construct the sample image set for model fitting (resizing is done here!)
    #         working_shape = (model.working_size, model.working_size)
    #         images = np.empty((nimages,) + working_shape, dtype=np.float32)
    #         for s in range(nimages):
    #             image = self.reader.read(s, c)
    #             image = model._resize_to_working_size(image[None, None, ...])
    #             images[s] = image[0, 0, :, :]
    #         model.working_size = None   # turn off automatic resizing after this

    #         # model fitting
    #         model.fit(images)     # fit the model
    #         models.append(model)  # store the fitted model

    #     # extract flatfield, darkfield, & baseline
    #     self.flatfield = np.empty((nchannels,) + image_shape, dtype=np.float32)
    #     self.darkfield = np.empty((nchannels,) + image_shape, dtype=np.float32)
    #     self.baseline  = np.empty((nchannels,) + (nimages,),  dtype=np.float32)
    #     for c in range(nchannels):
    #         self.flatfield[c] = skimage_size(models[c].flatfield, image_shape)
    #         self.darkfield[c] = skimage_size(models[c].darkfield, image_shape)
    #         self.baseline[c]  = models[c].baseline

    #     # save flatfield and darkfield as TIFF files (for ashlar integration)
    #     tifffile.imwrite(self.ffp_path, self.flatfield)
    #     tifffile.imwrite(self.dfp_path, self.darkfield)



# --------------------------------------------------------------------------------------
# add 2 extra properties to reg.BioformatsMetadata
# 1. channels          - list of channel information (name and color)
# 2. omexml            - OME-XML metadata as string
# class BioformatsMetadata2(reg.BioformatsMetadata):
#     def __init__(self, path):
#         super(BioformatsMetadata2, self).__init__(path)
#
#     @property
#     def channels(self):
#         if not hasattr(self, '_channels'):
#             self._channels = []
#             for channel in range(self.num_channels):
#                 ID   = self._metadata.getChannelID(0, channel)
#                 name = self._metadata.getChannelName(0, channel)
#                 c    = self._metadata.getChannelColor(0, channel)
#                 if c is not None:
#                     c = f"{c.getRed():02X}{c.getGreen():02X}{c.getBlue():02X}"
#                 self._channels.append({'ID': ID, 'name':  name, 'color': c,})
#         return self._channels
#
#     @property
#     def omexml(self):
#         import xml.etree.ElementTree as ET
#         import xml.dom.minidom as minidom
#     
#         xml_content = ET.tostring(
#             self._omexml_root,
#             encoding='utf-8',
#             xml_declaration=True,
#         ).decode('utf-8')
#
#         return minidom.parseString(xml_content).toprettyxml(indent="    ")



# --------------------------------------------------------------------------------------
# class BioformatsReader2(reg.BioformatsReader):
#     # replicate reg.BioformatsReader.__init__() by replacing metadata with BioformatsMetadata2
#     def __init__(self, path, plate=None, well=None):
#         self.path     = path
#         self.metadata = BioformatsMetadata2(self.path)
#         self.metadata.set_active_plate_well(plate, well)
#
#     def _block_reader(self, block, block_info=None, index=None):
#         # extract information about this block
#         info = block_info[None]
#         y0, y1 = info['array-location'][0]
#         x0, x1 = info['array-location'][1]
#         height = y1 - y0
#         width  = x1 - x0
#
#         bytes = self.metadata._reader.openBytes(index, x0, y0, width, height)
#         bytes = np.frombuffer(bytes.tostring(), dtype=block.dtype)
#
#         return bytes.reshape((height, width))
#
#     def to_dask_array(self, series, c, chunks=(512, 512)):
#         series = self.metadata.active_series[series]
#         self.metadata._reader.setSeries(series)
#         index = self.metadata._reader.getIndex(0, c, 0)  # t=0, c=channel, z=0
#         endidan = "<" if self.metadata._reader.isLittleEndian() else ">"
#         dtype = self.metadata.pixel_dtype.newbyteorder(endidan)
#         shape = self.metadata.tile_size(series)
#
#         # compose the dask array by mapping each chunk to _block_reader
#         dummy = da.empty(shape=shape, chunks=chunks, dtype=dtype) # the dummy dask array
#         return da.map_blocks(
#             self._block_reader,
#             dummy,
#             chunks=chunks,
#             dtype=dtype,
#             index=index,
#         )



