import sys
import argparse
from pathlib import Path

import numpy as np

from inky.auto import auto


def main():
    parser = argparse.ArgumentParser(
        description='Write an image to an Inky display')
    parser.add_argument('image_path', metavar='path', type=Path, help='Image to write')
    arguments = parser.parse_args()

    display = auto()

    image = display.buf
    if not py_encre.convert(str(arguments.image_path), py_encre.waveshare_7dot3_inch_e_paper_f_palette, image):
        print("Conversion failed")
        sys.exit(1)

    display.show()


if __name__ == '__main__':
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'build' / 'release' / 'py'))
    import py_encre

    py_encre.initialize(sys.argv[0])
    main()
    py_encre.uninitalize()
