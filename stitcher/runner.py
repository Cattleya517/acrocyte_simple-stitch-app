"""
runner.py — CLI wrapper for ashlar stitching, called by Electron.

Usage:
    python -m stitcher.runner /path/to/tile/directory

Prints plain-text progress to stdout for Electron to stream.
"""

import sys
import types

# Suppress Java/bioformats — not needed for TIFF stitching
sys.modules['javabridge'] = types.ModuleType('javabridge')
sys.modules['bioformats'] = types.ModuleType('bioformats')

import os
os.environ['MPLBACKEND'] = 'Agg'
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Flush stdout line-by-line so Electron receives live progress
sys.stdout.reconfigure(line_buffering=True)

from pathlib import Path
from .ashlar_adapter import FileSeriesReader2
from ashlar.reg import EdgeAligner, Mosaic, PyramidWriter


def main():
    if len(sys.argv) < 2:
        print("ERROR: No input directory provided")
        print("Usage: python -m stitcher.runner /path/to/tile/directory")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists() or not input_path.is_dir():
        print(f"ERROR: '{input_path}' is not a valid directory")
        sys.exit(1)

    print(f"Input directory: {input_path}")

    output_path = input_path / f"{input_path.name}_stitched.ome.tif"

    try:
        stitch(input_path, output_path)
    except Exception as e:
        print(f"ERROR: Stitching failed — {e}")
        sys.exit(1)

    print(f"Done! Output saved to: {output_path}")


def stitch(input_path, output_path):
    reader = FileSeriesReader2(input_path)
    edge_aligner = EdgeAligner(reader, channel=0, verbose=True)
    edge_aligner.run()

    mosaic = Mosaic(edge_aligner, shape=edge_aligner.mosaic_shape, verbose=True)
    PyramidWriter([mosaic], str(output_path), verbose=True).run()


if __name__ == "__main__":
    main()
