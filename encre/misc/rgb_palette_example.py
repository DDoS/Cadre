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

    # Some kind of e-ink kaleido display. It has rather awful color reproduction...
    # https://www.data-modul.com/sites/default/files/products/SA1452-EHA-specification-12051786.pdf
    palette = py_encre.make_palette_lab([
        py_encre.CIELab(5, 0, 0), # Missing from data sheet, just a guess
        py_encre.CIELab(32.81, 5.29, 0.12),
        py_encre.CIELab(35.99, -8.52, 2.97),
        py_encre.CIELab(33.04, -4.19, -8.16)
    ], target_luminance=90)

    image = np.zeros((480, 800), np.uint8)
    if not py_encre.convert(str(arguments.image_in_path), palette, image,
                            preview_image_path=str(arguments.image_out_path)):
        print("Conversion failed")
        sys.exit(1)

if __name__ == '__main__':
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'build' / 'release' / 'py'))
    import py_encre

    py_encre.initialize(sys.argv[0])
    main()
    py_encre.uninitalize()
