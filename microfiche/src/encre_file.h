#pragma once

#include <lwip/pbuf.h>

#include <stdbool.h>
#include <stdalign.h>

#include "GDEP073E01.h"

#define ENCRE_MAGIC_SIZE 6
#define ENCRE_WIDTH GDEP073E01_WIDTH
#define ENCRE_HEIGHT GDEP073E01_HEIGHT
#define ENCRE_PALETTE_SIZE GDEP073E01_PALETTE_SIZE
#define ENCRE_BITS_PER_COLOR GDEP073E01_BITS_PER_COLOR
#define ENCRE_COLOR_BYTES ((ENCRE_WIDTH * ENCRE_HEIGHT * ENCRE_BITS_PER_COLOR + 7) / 8)

enum rotation : uint8_t {
    automatic,
    landscape,
    portrait,
    landscape_upside_down,
    portrait_upside_down
};

struct encre_file_header {
    alignas(4) uint8_t magic[ENCRE_MAGIC_SIZE];
    uint8_t bits_per_color;
    enum rotation rotation;
    uint16_t palette_size;
    uint16_t width, height;
};

struct encre_file_body {
    float palette[ENCRE_PALETTE_SIZE][3];
    uint8_t colors[ENCRE_COLOR_BYTES];
};

struct encre_file {
    struct encre_file_header header;
    struct encre_file_body body;
};

struct encre_file_context {
    struct encre_file file;
    size_t offset;
    bool read_header;
    bool read_palette;
    bool read_colors;
};

void begin_encre_file(struct encre_file_context *file);
bool continue_encre_file(struct encre_file_context *file, const void* buffer, size_t size);
