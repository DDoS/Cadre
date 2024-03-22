#include "lightness.hpp"

#include "encre.hpp"

#include <vips/vips8>

namespace {
    int percentile(std::span<const uint32_t> histogram, uint32_t total_sum, double percent) {
        const auto percentile_sum = percent * total_sum;
        auto prefix_sum = 0u;
        for (int x = 0; x < histogram.size(); x++) {
            prefix_sum += histogram[x];
            if (static_cast<double>(prefix_sum) >= percentile_sum) {
                return x;
            }
        }

        return histogram.size();
    }

    void auto_exposure_and_brightness(vips::VImage lightness, const glm::vec2& target_min_max,
            std::optional<float>& exposure, std::optional<float>& brightness) {
        const auto histogram_offset = static_cast<float>(lightness.min());
        const auto histogram = (lightness + histogram_offset).hist_find();
        const auto histogram_region = vips::VRegion::new_from_image(histogram);
        histogram_region.prepare(0, 0, histogram.width(), 1);
        const auto histogram_rectangle = histogram_region.valid();
        const auto histogram_data = std::span{reinterpret_cast<const uint32_t*>(histogram_region.addr(histogram_rectangle.left, histogram_rectangle.top)),
                static_cast<size_t>(histogram_rectangle.width)};
        const auto histogram_total = lightness.width() * lightness.height();

        // Compute source dynamic range as 5% to 95% percentile, which will be the "range of interest".
        static constexpr auto outlier_threshold = 0.05;
        const auto source_min_max = glm::vec2{percentile(histogram_data, histogram_total, outlier_threshold),
                percentile(histogram_data, histogram_total, 1 - outlier_threshold)} - histogram_offset;

        const auto target_range = target_min_max.y - target_min_max.x;
        const auto range_overlap = std::max(0.f, std::min(source_min_max.y, target_min_max.y) - std::max(source_min_max.x, target_min_max.x));
        auto overlap_percentage = range_overlap / target_range;

        // Only do correction if there is less than 100% overlap of the source and target dynamic ranges.
        // Scale the strength of the corrections by the inverse of the overlap percentage.
        if (overlap_percentage < 1) {
            if (!exposure) {
                // Stretch the histogram to better fit the source range inside the target, but don't grow or shrink by more than 25%.
                const auto source_range = source_min_max.y - source_min_max.x;
                exposure = glm::mix(std::clamp(target_range / source_range, 0.75f, 1.25f),
                        encre::Options::no_exposure_change, overlap_percentage);
            }
            if (!brightness) {
                // Shift the histogram up or down towards the nearest target boundary
                const auto shift_min_max = target_min_max - exposure.value() * source_min_max;
                const auto absolute_shift = glm::abs(shift_min_max);
                brightness = glm::mix(absolute_shift.x < absolute_shift.y ? shift_min_max.x : shift_min_max.y,
                        encre::Options::no_brightness_change, overlap_percentage);
            }
        }

        if (!exposure) {
            exposure = encre::Options::no_exposure_change;
        }
        if (!brightness) {
            brightness = encre::Options::no_brightness_change;
        }
    }

    vips::VImage apply_exposure_and_brightness(vips::VImage lightness, const glm::vec2& target_min_max,
            std::optional<float> exposure, std::optional<float> brightness) {
        if (!exposure || !brightness) {
            auto_exposure_and_brightness(lightness, target_min_max, exposure, brightness);
        }

        return lightness * exposure.value() + brightness.value();
    }

    vips::VImage tone_map(vips::VImage lightness, const glm::vec2& target_min_max, float contrast) {
        // Sigmoid function to remap [-inf, inf] to [target_min, target_max]
        const auto target_range = target_min_max.y - target_min_max.x;
        const auto target_average = (target_min_max.x + target_min_max.y) / 2;
        return target_range / (1 + (contrast * (target_average - lightness)).exp()) + target_min_max.x;
    }
}

namespace encre {
    vips::VImage adjust_lightness(vips::VImage in, const Palette& palette, float dynamic_range,
            const std::optional<float>& exposure, const std::optional<float>& brightness, float contrast) {
        auto lightness = in.extract_band(0);

        const auto target_min_max = palette.gray_line * glm::vec2{dynamic_range, 2 - dynamic_range};
        lightness = apply_exposure_and_brightness(lightness, target_min_max, exposure, brightness);
        lightness = tone_map(lightness, target_min_max, contrast);

        return lightness.bandjoin(in.extract_band(1, vips::VImage::option()->set("n", in.bands() - 1)));
    }
}
