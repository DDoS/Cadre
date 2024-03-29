#pragma once

#include "encre.hpp"

namespace vips {
    class VImage;
}

namespace encre {
    void dither(vips::VImage& in, const Palette& palette, float clipped_chroma_recovery, std::span<uint8_t> result);
}
