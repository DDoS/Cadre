#pragma once

#include "encre.hpp"

namespace vips {
    class VImage;
}

namespace encre {
    void dither(vips::VImage& in, const Palette& palette, float lightness_adaptation_factor, std::span<uint8_t> result);
}