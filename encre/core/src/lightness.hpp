#pragma once

#include <optional>

namespace vips {
    class VImage;
}

namespace encre {
    struct Palette;

    vips::VImage adjust_lightness(vips::VImage in, const Palette& palette, float dynamic_range,
            const std::optional<float>& exposure, const std::optional<float>& brightness, float contrast);
}
