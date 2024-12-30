#pragma once

#include <stdint.h>

#define GDEP073E01_WIDTH 800
#define GDEP073E01_HEIGHT 480
#define GDEP073E01_PALETTE_SIZE 6
#define GDEP073E01_BITS_PER_COLOR 3

void GDEP073E01_write_image(const uint8_t *color_bits);
