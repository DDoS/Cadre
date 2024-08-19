#! /usr/bin/env python3

import argparse
import math

from display_protocol import Display


def import_display_module(name: str) -> Display:
    try:
        display_module = import_module(f'{name}')
        return display_module.init_display()
    except ModuleNotFoundError:
        print('Display module not found, will simulate instead')
        from simulated import Simulated
        return Simulated()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Write a test pattern to a display')
    parser.add_argument('display', metavar='name', type=str, help='Name of the display',
                        choices={'Simulated', 'pimoroni_inky', 'GDEP073E01'})
    parser.add_argument('--palette-size', metavar='number', type=int,
                        default=7, help='Number of palette elements')
    arguments = parser.parse_args()

    display: Display = import_display_module(arguments.display)

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
