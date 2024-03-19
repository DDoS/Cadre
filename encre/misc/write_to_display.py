#! /usr/bin/env python3

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


def parse_options(options_dict: dict[str]) -> 'py_encre.Option':
    options = py_encre.Options()

    if rotation := options_dict.get('rotation'):
        options.rotation = getattr(py_encre.Rotation, rotation)

    for name in ['contrast_coverage_percent', 'contrast_compression', 'clipped_gamut_recovery']:
        if value := options_dict.get(name):
            setattr(options, name, float(value))

    return options


def main():
    parser = argparse.ArgumentParser(
        description='Write an image to an Inky display')
    parser.add_argument('image_path', metavar='path', type=Path, help='Image to write')
    parser.add_argument('--out', metavar='path', type=Path, required=False, default=None,
                        help='Optional dithered image output')
    parser.add_argument('--status', action='store_true', help='Print status')
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

    options = parse_options(json.loads(arguments.options))

    out_path: str = None
    if arguments.out:
        out_path = str(arguments.out)

    if not py_encre.convert(str(arguments.image_path), py_encre.waveshare_7dot3_inch_e_paper_f_palette,
                            image, options=options, dithered_image_path=out_path):
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
