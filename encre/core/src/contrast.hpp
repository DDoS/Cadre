#pragma once

namespace vips {
    class VImage;
}

namespace encre {
    struct Palette;

    vips::VImage limit_contrast(vips::VImage in, const Palette& palette, float factor);
}
