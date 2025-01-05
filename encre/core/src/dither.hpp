#pragma once

#include "encre.hpp"

namespace vips {
    class VImage;
}

namespace encre {
    void dither(vips::VImage& in, const Palette& palette, bool hue_dependent_chroma_clamping, float clipped_chroma_recovery,
            float error_attenuation, std::span<uint8_t> result);
}
