#include "encre_file.h"

#include <pico/platform/compiler.h>

#include <stdint.h>
#include <string.h>

static const uint8_t encre_magic[ENCRE_MAGIC_SIZE] = "encre";

void begin_encre_file(struct encre_file_context *context) {
    context->offset = 0;
    context->read_header = false;
    context->read_palette = false;
    context->read_colors = false;
}

bool continue_encre_file(struct encre_file_context *context, const void* buffer, size_t size) {
    static const size_t file_size = sizeof(context->file);
    static const size_t header_size = sizeof(context->file.header);
    static const size_t palette_size = sizeof(context->file.body.palette);
    static const size_t colors_size = sizeof(context->file.body.colors);

    if (context->offset + size > file_size) {
        return false;
    }

    memcpy((char*)&context->file + context->offset, buffer, size);
    context->offset += size;

    if (!context->read_header && context->offset >= header_size) {
        context->read_header = true;
        if (memcmp(context->file.header.magic, encre_magic, ENCRE_MAGIC_SIZE) != 0 ||
                context->file.header.bits_per_color != ENCRE_BITS_PER_COLOR ||
                context->file.header.palette_size != ENCRE_PALETTE_SIZE ||
                context->file.header.width != ENCRE_WIDTH ||
                context->file.header.height != ENCRE_HEIGHT) {
            return false;
        }
    }

    if (!context->read_palette && context->offset >= header_size + palette_size) {
        context->read_palette = true;
    }

    if (!context->read_colors && context->offset == file_size) {
        context->read_colors = true;
    }

    return true;
}
