import sys
import argparse
from pathlib import Path

import numpy as np

def main():
    parser = argparse.ArgumentParser(
        description='Convert an image with a custom palette')
    parser.add_argument('image_in_path', metavar='path', type=Path, help='Image to convert')
    parser.add_argument('image_out_path', metavar='path', type=Path, help='Converted image')
    arguments = parser.parse_args()

    # Black, sRGB primaries, and white
    palette = py_encre.make_palette_xyz([
        py_encre.CIEXYZ(0, 0, 0),
        py_encre.CIEXYZ(41.246, 21.267, 1.933),
        py_encre.CIEXYZ(35.758, 71.515, 11.919),
        py_encre.CIEXYZ(18.044, 7.217, 95.03),
        py_encre.CIEXYZ(95.047, 100, 108.883)
    ], target_luminance=100)

    image = np.zeros((480, 800), np.uint8)
    if not py_encre.convert(str(arguments.image_in_path), palette, image,
                            str(arguments.image_out_path), lightness_adaptation_factor=0):
        print("Conversion failed")
        sys.exit(1)

if __name__ == '__main__':
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'build' / 'release' / 'py'))
    import py_encre

    py_encre.initialize(sys.argv[0])
    main()
    py_encre.uninitalize()
