#! /usr/bin/env python3 -u

import sys
import argparse
import json
from pathlib import Path

inky_available = False
try:
    from inky.auto import auto
    inky_available = True
except ModuleNotFoundError:
    print('Inky module not found, will simulate instead')


def main():
    parser = argparse.ArgumentParser(
        description='Write an image to an Inky display')
    parser.add_argument('image_path', metavar='path', type=Path, help='Image to write')
    parser.add_argument('--preview', metavar='path', type=Path, required=False, default=None,
                        help='Optional preview image output')
    parser.add_argument('--status', action='store_true', help='Print status')
    parser.add_argument('--palette', metavar='name', type=str, required=False,
                        default='waveshare_7_color', help='Display palette name')
    parser.add_argument('--options', metavar='json', type=str, required=False, default={},
                        help='Options as a JSON encoded string')
    arguments = parser.parse_args()

    if inky_available:
        display = auto()
        image = display.buf
    else:
        import numpy
        image = numpy.zeros((480, 800), numpy.uint8)

    if arguments.status:
        print('Status: CONVERTING')

    palette = py_encre.palette_by_name[arguments.palette]

    if arguments.options:
        options = py_encre.Options(**json.loads(arguments.options))
    else:
        options = py_encre.Options()

    preview_path: str = None
    if arguments.preview:
        preview_path = str(arguments.preview)

    if not py_encre.convert(str(arguments.image_path), palette, image,
                            options=options, preview_image_path=preview_path):
        print('Conversion failed')
        sys.exit(1)

    if arguments.status:
        print('Status: DISPLAYING')

    if inky_available:
        display.show()
    else:
        import time
        time.sleep(5)


if __name__ == '__main__':
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'build/release/py'))
    import py_encre

    py_encre.initialize(sys.argv[0])
    main()
    py_encre.uninitalize()
