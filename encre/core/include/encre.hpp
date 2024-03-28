#pragma once

#include "encre_export.hpp"

#include <glm/glm.hpp>

#include <cstdint>
#include <string>
#include <vector>
#include <span>
#include <map>

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

        std::vector<Oklab> gamut_vertices;
        std::vector<Plane> gamut_hull;
        glm::vec2 gray_line;
    };

    enum class Rotation {
        automatic,
        landscape,
        portrait,
        landscape_upside_down,
        portrait_upside_down
    };

    struct Options {
        static constexpr Rotation default_rotation = Rotation::automatic;
        static constexpr float default_dynamic_range = 0.95f;
        static constexpr float default_contrast = 0.065f;
        static constexpr std::nullopt_t automatic_exposure = std::nullopt;
        static constexpr std::nullopt_t automatic_brightness = std::nullopt;
        static constexpr float no_exposure_change = 1;
        static constexpr float no_brightness_change = 0;
        static constexpr float default_sharpening = 4;
        static constexpr float default_clipped_chroma_recovery = 1.f;

        Rotation rotation = default_rotation;
        float dynamic_range = default_dynamic_range;
        std::optional<float> exposure = automatic_exposure;
        std::optional<float> brightness = automatic_brightness;
        float contrast = default_contrast;
        float sharpening = default_sharpening;
        float clipped_chroma_recovery = default_clipped_chroma_recovery;
    };

    // Using std::map to keep the name ordering consistent
    ENCRE_EXPORT extern const std::map<std::string, encre::Rotation> rotation_by_name;

    // Builtin palette for https://www.waveshare.com/7.3inch-e-paper-hat-f.htm
    ENCRE_EXPORT extern const Palette waveshare_7dot3_inch_e_paper_f_palette;

    ENCRE_EXPORT void initialize(const char* executable_path);

    ENCRE_EXPORT void uninitalize();

    ENCRE_EXPORT Palette make_palette(std::span<const CIEXYZ> colors, float target_luminance = Palette::default_target_luminance);

    ENCRE_EXPORT Palette make_palette(std::span<const CIELab> colors, float target_luminance = Palette::default_target_luminance);

    ENCRE_EXPORT bool convert(const char* image_path, uint32_t width, uint32_t height, const Palette& palette, const Options& options,
            std::span<uint8_t> output, const char* preview_image_path = nullptr);
}
