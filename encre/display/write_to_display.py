#! /usr/bin/env -S python3 -u

import sys
import argparse
import json
from pathlib import Path
from importlib import import_module

from display_protocol import Display


def import_display_module(name: str, config) -> Display:
    try:
        display_module = import_module(f'{name}')
        return display_module.init_display(config)
    except ModuleNotFoundError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Write an image to a display')
    parser.add_argument('display', metavar='name', type=str, help='Name of the display',
                        choices={'simulated', 'proxy', 'pimoroni_inky', 'GDEP073E01', 'microfiche'})
    parser.add_argument('--display-config', metavar='json', type=str, required=False, default=None,
                        help='Display config as a JSON encoded string')
    parser.add_argument('image_path', metavar='path', type=Path, help='Image to write')
    parser.add_argument('--preview', metavar='path', type=Path, required=False, default=None,
                        help='Optional preview image output')
    parser.add_argument('--status', action='store_true', help='Print status')
    parser.add_argument('--palette', metavar='name', type=str, required=False,
                        default='waveshare_gallery_palette', help='Display palette name')
    parser.add_argument('--options', metavar='json', type=str, required=False, default=None,
                        help='Options as a JSON encoded string')
    parser.add_argument('--info', metavar='json', type=str, required=False, default=None,
                        help='Image info as a JSON encoded string')
    arguments = parser.parse_args()

    display_config = {}
    if arguments.display_config:
        display_config = json.loads(arguments.display_config)

    palette = py_encre.palette_by_name[arguments.palette]

    if arguments.options:
        options = py_encre.Options(**json.loads(arguments.options))
    else:
        options = py_encre.Options()

    info = {}
    if arguments.info:
        info = json.loads(arguments.info)

    display: Display = import_display_module(arguments.display, display_config)
    if not display:
        print('Failed to initialize the display module', file=sys.stderr)
        return 1

    if arguments.status:
        print('Status: CONVERTING')

    preview_path: str = None
    if arguments.preview:
        preview_path = str(arguments.preview)

    output_rotation = py_encre.read_compatible_encre_file(str(arguments.image_path),
                                                          len(palette.points), display.buf)
    if not output_rotation:
        output_rotation = py_encre.convert(str(arguments.image_path), palette,
                                           display.buf, options=options)
    if not output_rotation:
        print('Conversion failed', file=sys.stderr)
        return 1

    if preview_path and not py_encre.write_preview(display.buf, palette.points,
                                                   output_rotation, preview_path):
        print('Preview creation failed', file=sys.stderr)
        return 1

    if arguments.status:
        print('Status: DISPLAYING')

    try:
        setattr(display, 'palette', palette)
    except AttributeError:
        pass
    try:
        setattr(display, 'output_rotation', output_rotation)
    except AttributeError:
        pass
    try:
        setattr(display, 'info', info)
    except AttributeError:
        pass

    display.show()
    return 0


if __name__ == '__main__':
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'build/release/py'))
    import py_encre

    py_encre.initialize(sys.argv[0])
    try:
        result = main()
    finally:
        py_encre.uninitalize()
    sys.exit(result)
