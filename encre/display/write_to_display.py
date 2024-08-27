#! /usr/bin/env -S python3 -u

from importlib import import_module
import sys
import argparse
import json
from pathlib import Path

from display_protocol import Display


def import_display_module(name: str) -> Display:
    try:
        display_module = import_module(f'{name}')
        return display_module.init_display()
    except ModuleNotFoundError:
        print('Display module not found, will use "simulated" instead')
        from simulated import Simulated
        return Simulated()


def main():
    parser = argparse.ArgumentParser(
        description='Write an image to a display')
    parser.add_argument('display', metavar='name', type=str, help='Name of the display',
                        choices={'simulated', 'pimoroni_inky', 'GDEP073E01'})
    parser.add_argument('image_path', metavar='path', type=Path, help='Image to write')
    parser.add_argument('--preview', metavar='path', type=Path, required=False, default=None,
                        help='Optional preview image output')
    parser.add_argument('--status', action='store_true', help='Print status')
    parser.add_argument('--palette', metavar='name', type=str, required=False,
                        default='waveshare_gallery_palette', help='Display palette name')
    parser.add_argument('--options', metavar='json', type=str, required=False, default={},
                        help='Options as a JSON encoded string')
    arguments = parser.parse_args()

    display: Display = import_display_module(arguments.display)

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

    if not py_encre.convert(str(arguments.image_path), palette, display.buf,
                            options=options, preview_image_path=preview_path):
        print('Conversion failed')
        sys.exit(1)

    if arguments.status:
        print('Status: DISPLAYING')

    display.show()


if __name__ == '__main__':
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'build/release/py'))
    import py_encre

    py_encre.initialize(sys.argv[0])
    main()
    py_encre.uninitalize()
