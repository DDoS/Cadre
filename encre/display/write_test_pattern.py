#! /usr/bin/env -S python3 -u

import argparse
import json
import math
import sys
from importlib import import_module

from display_protocol import Display


def import_display_module(name: str, config) -> Display:
    try:
        display_module = import_module(f'{name}')
        return display_module.init_display(config)
    except ModuleNotFoundError:
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Write a test pattern to a display')
    parser.add_argument('display', metavar='name', type=str, help='Name of the display',
                        choices={'simulated', 'proxy', 'pimoroni_inky', 'GDEP073E01'})
    parser.add_argument('--display-config', metavar='json', type=str, required=False, default=None,
                        help='Display config as a JSON encoded string')
    parser.add_argument('--palette-size', metavar='number', type=int,
                        default=7, help='Number of palette elements')
    arguments = parser.parse_args()

    display_config = {}
    if arguments.display_config:
        display_config = json.loads(arguments.display_config)

    display: Display = import_display_module(arguments.display, display_config)
    if not display:
        print('Failed to initialize the display module', file=sys.stderr)
        sys.exit(1)

    height, width = display.buf.shape
    block_size = max(50, min(100, math.gcd(height, width) / 2))
    block_count = arguments.palette_size
    blocks_per_line = width // block_size
    for y in range(0, height):
        yb = y // block_size
        for x in range(0, width):
            xb = x // block_size
            block_index = xb + blocks_per_line * yb
            display.buf[y, x] = block_index % block_count

    display.show()
