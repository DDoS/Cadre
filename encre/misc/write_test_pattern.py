#! /usr/bin/env python3

import argparse
import math

import numpy
from inky.auto import auto

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Write a test pattern to an Inky display')
    parser.add_argument('--palette-size', metavar='number', type=int,
                        default=7, help='Number of palette elements')
    arguments = parser.parse_args()

    display = auto()

    image: numpy.ndarray = display.buf

    height, width = image.shape
    block_size = max(50, min(100, math.gcd(height, width) / 2))
    block_count = arguments.palette_size
    blocks_per_line = width // block_size
    for y in range(0, height):
        yb = y // block_size
        for x in range(0, width):
            xb = x // block_size
            block_index = xb + blocks_per_line * yb
            image[y, x] = block_index % block_count

    display.show()
