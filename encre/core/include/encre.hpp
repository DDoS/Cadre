#pragma once

#include "encre_export.hpp"

#include <glm/glm.hpp>

#include <cstdint>
#include <vector>
#include <span>

namespace encre {
    struct XYZ : glm::vec3 {
        using glm::vec3::vec3;

        constexpr explicit XYZ(const glm::vec3& v) : glm::vec3(v) {
        }
    };

    struct CIEXYZ : XYZ {
        using XYZ::XYZ;

        constexpr explicit CIEXYZ(const glm::vec3& v) : XYZ(v) {
        }
    };

    struct Lab : glm::vec3 {
        using glm::vec3::vec3;

        constexpr explicit Lab(const glm::vec3& v) : glm::vec3(v) {
        }
    };

    struct CIELab : Lab {
        using Lab::Lab;

        constexpr explicit CIELab(const glm::vec3& v) : Lab(v) {
        }
    };

    struct Oklab : Lab {
        using Lab::Lab;

        constexpr explicit Oklab(const glm::vec3& v) : Lab(v) {
        }
    };

    struct Plane : glm::vec4 {
        using glm::vec4::vec4;
    };

    struct Palette {
        static constexpr float default_target_luminance = 80;

        std::vector<Oklab> elements;
        std::vector<Plane> gamut_hull;
        glm::vec2 gray_line;
    };

    struct Options {
        static constexpr float default_contrast_coverage_percent = 0.95f;
        static constexpr float default_contrast_compression = 0.065f;
        static constexpr float default_clipped_gamut_recovery = 0.5f;

        float contrast_coverage_percent = default_contrast_coverage_percent;
        float contrast_compression = default_contrast_compression;
        float clipped_gamut_recovery = default_clipped_gamut_recovery;
    };

    // Builtin palette for https://www.waveshare.com/7.3inch-e-paper-hat-f.htm
    ENCRE_EXPORT extern const Palette waveshare_7dot3_inch_e_paper_f_palette;

    ENCRE_EXPORT void initialize(const char* executable_path);

    ENCRE_EXPORT void uninitalize();

    ENCRE_EXPORT Palette make_palette(std::span<const CIEXYZ> colors, float target_luminance = Palette::default_target_luminance);

    ENCRE_EXPORT Palette make_palette(std::span<const CIELab> colors, float target_luminance = Palette::default_target_luminance);

    ENCRE_EXPORT bool convert(const char* image_path, uint32_t width, uint32_t height, const Palette& palette, const Options& options,
            std::span<uint8_t> output, const char* dithered_image_path = nullptr);
}