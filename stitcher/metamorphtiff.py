import re
from pathlib import Path
from tqdm import tqdm
import numpy as np
import pandas as pd
import tifffile
import xml.etree.ElementTree as ET

from ._channelinfo import name_to_title, name_to_rank



# --------------------------------------------------------------------------------------
# MD (Molecular Devices) image filename pattern
# 1. plate_name   - image name          (any string)
# 2. well_name    - well name           (a letter followed by two digits)
# 3. series_idx   - tile series number  (an integer)
# 4. channel_idx  - tile channel number (0-9)
# 5. examples:
#    a. ACT019 m o D7 HER2 PBMC RCE Na_A01_s1_w1D1ABFAEB-4BF2-483B-9BE6-82026AEC8815.tif
#    b. ACT019 m o D7 HER2 PBMC RCE Na_A01_s1_w42EC4E850-1925-4875-8B6D-4F0726635069.tif
#MD_PATTERN = r'(?P<plate_name>[\s\S]+)_(?P<well_name>[A-Z]\d{2})_s(?P<series_idx>\d+)_w(?P<channel_idx>\d)[A-Z\d-]+\.tif'
#MD_PATTERN = r'(?P<plate_name>[\s\S]+)_(?P<well_name>[A-Z]\d{2})_[A-Z\d-]+\.tif'
MD_PATTERN = r'(?P<plate_name>.+)_(?P<well_name>[A-Z]\d{2})_.+\.tiff?'


# --------------------------------------------------------------------------------------
# 1. MetaMorph TIFF documentation is at: 
#    a. https://support.moleculardevices.com/s/article/MetaMorph-Software-TIFF-and-STK-file-formats? 
#    b. every image file is a single-plane TIFF file compliant with the TIFF 6.0 specification
# 2. to_dataframe() - scan the directory for matched image files and extract metadata into a pandas DataFrame
class MetaMorphTIFFHelper:
    def __init__(self, path, pattern=MD_PATTERN):
        self.path    = path
        self.pattern = pattern
    
    # ---------------------------------------------------------------------
    # convert the collected image files and metadata into a pandas DataFrame
    def to_dataframe(self):
        records = []
        self._collect_image_files(records)
        self._extract_image_metadata(records)
        self._sort_raster_order(records)
        return self._convert_to_dataframe(records)
    
    # ---------------------------------------------------------------------
    @staticmethod
    def filter(df, plate_idx=0, well_idx=0, series_idx=None, channel_idx=None):
        assert plate_idx is not None, "plate_idx must be specified"
        
        if well_idx is None:
            db = df.loc[pd.IndexSlice[plate_idx, :, :], :]
        elif series_idx is None:
            db = df.loc[pd.IndexSlice[plate_idx, well_idx, :], :]
        else:
            db = df.loc[pd.IndexSlice[plate_idx, well_idx, series_idx], :]
        if channel_idx is None:
            return db
        elif not isinstance(channel_idx, list):
            channel_idx = [channel_idx]

        assert all(c < len(db.iloc[0]['channel_name']) for c in channel_idx), "invalid channel index"

        db = db.copy()  # create a copy to avoid in-place modification
        db["channel_name"] = [tuple(cn[i] for i in channel_idx) for cn in db["channel_name"]]
        db["file_path"]    = [tuple(fp[i] for i in channel_idx) for fp in db["file_path"]]
        return db

    # ---------------------------------------------------------------------
    # for my own convenience, rename channel names to something I am familiar with
    @staticmethod
    def rename_channels(df):
        df = df.copy()  # create a copy to avoid in-place modification
        df['channel_name'] = [tuple(name_to_title(c) or c for c in channels) for channels in df['channel_name']]
        return df

    # ---------------------------------------------------------------------
    # add images to the newly created SpatialData object (memory-persistent)
    # 1. add each image as a images layer indexed by (plate_idx, well_idx, series_idx)
    #    a. plate_idx and well_idx are specified before extracting the database
    #    b. series_idx is the index of the image in the current well
    # 2. specify the transformations for each image:
    #    a. 'global': no translation (for convenience)
    #    b. 'pixel':  translation to reflect its relative position among series images
    #    c. 'micron': include scale to convert pixel to micron units
    # 3. MetaMorph TIFF uses 1-based indexing for series and channel, 
    #    a. the image layer name uses the 1-based series indexing (consistent with the original file naming)
    #    b. the channels are indexed by their names instead of their indices (no worry about 0-based vs 1-based)
    # 4. sdata["s1"] = spatialdata.models.Image2DModel.parse() to add dask image to sdata
    #    a. images layer "s1" is a dask array with dims ('c', 'y', 'x')
    #    b. no data is loaded into memory until requested
    #    c. this stays the same even if sdata was  backed by a zarr store!
    @staticmethod
    def to_spatialdata(df, chunks=(1, 1024, 1024), coordinate_systems=None, scale_factors=None):
        import spatialdata as sd
        import spatialdata.transformations as st
        # specify pixel sizes
        pixel_size = df.iloc[0]['pixel_size']    # in microns
        scale      = st.Scale(axes=["y", "x"], scale=[pixel_size, pixel_size])

        # read image files and extract the stage positions (in pixels) as translation transformations
        series_idx, images, translations = MetaMorphTIFFHelper._extract_images(df, chunks)

        # check coordinate systems
        if coordinate_systems is None:
            coordinate_systems = ['micron']
        elif not isinstance(coordinate_systems, list):
            coordinate_systems = [coordinate_systems]
        assert set(coordinate_systems).issubset({'global', 'pixel', 'micron'}), "unsupported coordinate system"

        # add images to sdata with appropriate transformations and metadata
        sdata = sd.SpatialData()
        for i, (s, translation, image) in enumerate(zip(series_idx, translations, images)):
            T = {'global': st.Identity(), 'pixel': translation, 'micron': st.Sequence([translation, scale])}
            sdata[f"s{s+1}"] = sd.models.Image2DModel.parse(    # make it 1-based indexing for series
                data=image,
                dims=['c', 'y', 'x'],
                transformations={cs: T[cs] for cs in coordinate_systems},
                scale_factors=scale_factors,
                c_coords=list(df.iloc[i]['channel_name']),
            )

        return sdata
    
    # ---------------------------------------------------------------------
    @staticmethod
    def plate_names(df):
        return df['plate_name'].unique().tolist()

    # ---------------------------------------------------------------------
    @staticmethod
    def well_names(df, plate_idx=0):
        return df.loc[plate_idx, 'well_name'].unique().tolist()

    # ---------------------------------------------------------------------
    @staticmethod
    def series_ids(df, plate_idx=0, well_idx=0):
        return df.loc[pd.IndexSlice[plate_idx, well_idx, :], :].index.levels[2].tolist()

    # ---------------------------------------------------------------------
    @staticmethod
    def channel_names(df, plate_idx=0, well_idx=0):
        return list(df.loc[pd.IndexSlice[plate_idx, well_idx, :], "channel_name"].iloc[0])

    # ---------------------------------------------------------------------
    @staticmethod
    def file_paths(df, plate_idx=0, well_idx=0, series_idx=0):
        return list(df.loc[pd.IndexSlice[plate_idx, well_idx, series_idx], "file_path"])

    # ---------------------------------------------------------------------
    # collect all image files matching the filename pattern MD_PATTERN
    # 1. only examine the file size larger than min_filesize (default: 1MB)
    # 2. this is to exclude the thumbnail files
    def _collect_image_files(self, records, min_filesize=1_000_000):
        all_files = [p for p in self.path.iterdir() if p.is_file() and not p.name.startswith('._')]
        all_files = [p for p in all_files if p.stat().st_size >= min_filesize]  # exclude thumbnail files
        for p in tqdm(all_files, desc="searching matched image filenames"):
            match = re.match(self.pattern, p.name)
            if match is not None:
                gd = match.groupdict()
                record = {
                    'plate_name':  gd['plate_name'],
                    'well_name':   gd['well_name'],
                    'series_idx':  None,    # will be extracted from metadata later
                    'channel_idx': None,    # will be extracted from metadata later,
                    'file_path':   str(p),  # make it hashable
                }
                records.append(record)

    # ---------------------------------------------------------------------
    # extract image metadata using tiffile.TiffFile
    def _extract_image_metadata(self, records):
        extracted_properties = [
            'pixel-size-x', 'pixel-size-y', 
            'bits-per-pixel',
            'spatial-calibration-x', 'spatial-calibration-y', 'spatial-calibration-units',
            'stage-position-x', 'stage-position-y',
            '_IllumSetting_',
        ]
        convert = {"int": int, "float": float, "string": str,}

        for record in tqdm(records, desc="extracting image metadata"):
            prop = {}
            with tifffile.TiffFile(record['file_path']) as tif:
                root = ET.fromstring(tif.pages[0].tags['ImageDescription'].value)
                for p in root.find('PlaneInfo').findall('prop'):
                    if p.attrib['id'] in extracted_properties:
                        prop[p.attrib['id']] = convert[p.attrib['type']](p.attrib['value'])
            assert prop['spatial-calibration-units'] == "um", "unsupported pixel size unit"
            assert prop['spatial-calibration-x'] == prop['spatial-calibration-y'], "non-square pixels are not supported"

            delta = prop['spatial-calibration-x']
            record['pixel_size']    = delta
            record['pixel_dtype']   = np.dtype(f"uint{prop['bits-per-pixel']}")
            record['tile_size']     = np.array([prop['pixel-size-y'], prop['pixel-size-x']])                # in pixels
            record['tile_position'] = np.array([prop['stage-position-y'], prop['stage-position-x']])/delta  # in pixels
            record['channel_name']  = prop.get('_IllumSetting_', str(record['channel_idx']))  # default to channel_idx if not found

    # ---------------------------------------------------------------------
    # sort records in raster order (top-to-bottom, left-to-right) based on tile_position
    # and assign series_idx (per plate+well group) and channel_idx (per series group)
    # tol is the tolerance for grouping tile positions (e.g. tol=10 means positions within 10 pixels are considered the same)
    @staticmethod
    def _sort_raster_order(records, tol=10):
        from itertools import groupby as itertools_groupby

        # bin tile_position by tolerance for grouping (e.g. tol=10 → positions within 10px bin together)
        for r in records:
            r['_pos'] = tuple((r['tile_position'] // tol).astype(int))

        # group records by (plate_name, well_name)
        key_well = lambda r: (r['plate_name'], r['well_name'])
        records.sort(key=key_well)

        for _, well_group in itertools_groupby(records, key=key_well):
            well_records = list(well_group)

            # group by rounded position, sort in raster order (Y, X)
            well_records.sort(key=lambda r: r['_pos'])
            series_idx = 0
            for _, pos_group in itertools_groupby(well_records, key=lambda r: r['_pos']):
                pos_records = sorted(pos_group, key=lambda r: name_to_rank(r['channel_name']))
                for channel_idx, r in enumerate(pos_records):
                    r['series_idx']  = series_idx
                    r['channel_idx'] = channel_idx
                series_idx += 1

        # clean up temporary key
        for r in records:
            del r['_pos']

    # ---------------------------------------------------------------------
    # convert records to a sorted multi-index pandas DataFrame
    def _convert_to_dataframe(self, records):
        # convert to a dataframe
        df = pd.DataFrame.from_records(records)

        # construct sorted multi-index dataframe
        df['plate_idx'] = df['plate_name'].astype('category').cat.codes             # plate index
        df['well_idx']  = (                                                         # well index within each plate
            df.groupby('plate_name')['well_name']
            .transform(lambda well_name: well_name.astype('category').cat.codes)
        )
        df = df.set_index(['plate_idx', 'well_idx', 'series_idx', 'channel_idx'])   # make multi-index DataFrame
        df = df.sort_index()                                                        # sort index

        # collect all file paths for each imaging location
        df = df.groupby(level=['plate_idx', 'well_idx', 'series_idx'], sort=False).agg({
            'plate_name':    'first',   # Plate name
            'well_name':     'first',   # Well name
            'pixel_size':    'first',   # Pixel size (should be consistent)
            'pixel_dtype':   'first',   # Pixel data type (should be consistent)
            'tile_size':     'first',   # Tile size (should be consistent)
            'tile_position': 'first',   # Position (should be same for all channels)
            'channel_name':  tuple,     # All channel names for this location
            'file_path':     tuple,     # All file paths for this location
        }).sort_index()                 # sort index for performance

        return df
    
    # ---------------------------------------------------------------------
    # read images using dask-image
    # 1. each tiff file is a single-channel image tile
    # 2. imread.imread() convert it to a dask array (1, y, x)
    # 3. da.squeeze() remove the channel dimension, resulting in (y, x)
    # 4. da.stack() stack all channel images along the channel axis, resulting in (c, y, x)
    # 5. rechunk() set the chunk size for better performance
    @staticmethod
    def _extract_images(df, chunks=None):
        from dask_image import imread
        import dask.array as da
        import spatialdata.transformations as st

        series_idx   = []
        translations = []
        images       = []
        for s in range(len(df)):
            row = df.iloc[s]

            # extract series index
            series_idx.append(row.name[2])  # ('plate_idx', 'well_idx', 'series_idx')

            # define the translation transformation based on tile position
            translation = st.Translation(
                axes=["y", "x"], 
                translation=list(row['tile_position']),
            )
            translations.append(translation)

            # construct the dask array for each image
            image = [da.squeeze(imread.imread(file_path)) for file_path in row['file_path']]
            image = da.stack(image, axis=0)     # stack along the channel axis
            if chunks is not None:
                image = image.rechunk(chunks)   # rechunk
            images.append(image)

        return series_idx, images, translations



# ---------------------------------------------------------------------
__all__ = [
    "MetaMorphTIFFHelper",
]


if __name__ == "__main__":
    # import argparse

    # parser = argparse.ArgumentParser(description="Debug MetaMorphTIFF2 helper")
    # parser.add_argument("-i", "--input", type=str, required=True, help="Path to the directory containing MetaMorph TIFF files")
    # parser.add_argument("--plate-idx", type=int, default=0, help="Plate index (default: 0)")
    # parser.add_argument("--well-idx", type=int, default=0, help="Well index (default: 0)")
    # args = parser.parse_args()

    # input_path = Path(args.input)
    # assert input_path.exists(), f"{input_path} does not exist"

    # for quick testing, you can hardcode the input path here
    input_path = Path.home() / "Downloads" / "T25w4701023-12"

    # Step 1: Scan directory and build dataframe
    helper = MetaMorphTIFFHelper(input_path)
#    df = helper.to_dataframe()
    records = []
    helper._collect_image_files(records)
    helper._extract_image_metadata(records)
    helper._sort_raster_order(records)


    for record in sorted(records, key=lambda r: r['series_idx']):
        print(f"series {record['series_idx']}: {record['tile_position']},  {Path(record['file_path']).name}")

    df = helper._convert_to_dataframe(records)







    print("\n--- DataFrame shape ---")
    print(df.shape)
    print("\n--- DataFrame columns ---")
    print(df.columns.tolist())
    print("\n--- DataFrame head ---")
    print(df.head())
    print("\n--- Plates ---")
    print(MetaMorphTIFFHelper.plate_names(df))
    print("\n--- Wells ---")
#    print(MetaMorphTIFFHelper.well_names(df, plate_idx=args.plate_idx))
#    print("\n--- Channels ---")
#    print(MetaMorphTIFFHelper.channel_names(df, plate_idx=args.plate_idx, well_idx=args.well_idx))
#    print("\n--- Series IDs ---")
#    print(MetaMorphTIFFHelper.series_ids(df, plate_idx=args.plate_idx, well_idx=args.well_idx))







