#include "encre.hpp"

#include <vips/vips8>

namespace encre {
    vips::VImage limit_contrast(vips::VImage in, const Palette& palette, float factor) {
        const auto low = palette.gray_line.x * 0.9f;
        const auto high = palette.gray_line.y * 1.1f;

        auto lightness = in.extract_band(0);
        lightness = low + (high - low) / (1 + (factor * ((low + high) / 2 - lightness)).exp());

        return lightness.bandjoin(in.extract_band(1, vips::VImage::option()->set("n", in.bands() - 1)));
    }
}
