#include "encre.hpp"

#include <vips/vips8>

namespace encre {
    vips::VImage limit_contrast(vips::VImage in, const Palette& palette, float coverage, float compression) {
        const auto low = palette.gray_line.x * coverage;
        const auto high = palette.gray_line.y * (2 - coverage);

        // Sigmoid function to remap [-inf, inf] to [low, high]
        auto lightness = in.extract_band(0);
        lightness = low + (high - low) / (1 + (compression * ((low + high) / 2 - lightness)).exp());

        return lightness.bandjoin(in.extract_band(1, vips::VImage::option()->set("n", in.bands() - 1)));
    }
}
