"""
runner.py — CLI wrapper for ashlar stitching, called by Electron.

Usage:
    python -m python.runner /path/to/tile/directory

Prints plain-text progress to stdout for Electron to stream.
"""

import sys
from pathlib import Path
from .ashlar_adapter import FileSeriesReader2
from ashlar.reg import EdgeAligner, Mosaic, PyramidWriter

def main():
    # --- Step 1: Parse input directory from CLI args ---
    if len(sys.argv) < 2:
        print("ERROR: No input directory provided")
        print("Usage: python -m python.runner /path/to/tile/directory")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists() or not input_path.is_dir():
        print(f"ERROR: '{input_path}' is not a valid directory")
        sys.exit(1)

    print(f"Input directory: {input_path}")

    # --- Step 2: Create reader, align, mosaic, and write ---
    # TODO: You implement stitch() below
    output_path = input_path / "stitched.ome.tif"
    stitch(input_path, output_path)

    print(f"Done! Output saved to: {output_path}")


def stitch(input_path, output_path):
    """
    Run the full ashlar stitching pipeline.

    This function should:
      1. Create a FileSeriesReader2 (the adapter that reads your MetaMorph TIFFs)
      2. Run EdgeAligner (refines tile positions using cross-correlation)
      3. Create a Mosaic (composites aligned tiles)
      4. Write via PyramidWriter (outputs OME-TIFF)

    Args:
        input_path:  Path to directory containing MetaMorph TIFF tiles
        output_path: Path for output OME-TIFF file

    Hints:
        - Look at python/ashlar_adapter.py:FileSeriesReader2 for step 1
        - Look at ashlar/scripts/ashlar.py:process_single() for steps 2-4
        - EdgeAligner(reader, channel=0, verbose=True).run()
        - Mosaic(edge_aligner, shape=edge_aligner.mosaic_shape, verbose=True)
        - PyramidWriter([mosaic], str(output_path), verbose=True).run()
    """
    reader = FileSeriesReader2(input_path)
    edge_aligner = EdgeAligner(reader, channel=0, verbose=True)
    edge_aligner.run()

    mosaic = Mosaic(edge_aligner, shape=edge_aligner.mosaic_shape, verbose=True)
    PyramidWriter([mosaic], str(output_path), verbose=True).run()


if __name__ == "__main__":
    main()
