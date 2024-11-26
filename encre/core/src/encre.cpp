#include "encre.hpp"

#include "oklab.hpp"
#include "lightness.hpp"
#include "dither.hpp"

#include <vips/vips8>

#include <iostream>
#include <cstdlib>

namespace {
    const std::vector<double> oklab_black{0, 0, 0};
    const std::vector<double> oklab_white{100, 0, 0};
}

namespace encre {
    // Using std::map to keep the name ordering consistent
    const std::map<std::string, Rotation> rotation_by_name{
        {"automatic", Rotation::automatic},
        {"landscape", Rotation::landscape},
        {"portrait", Rotation::portrait},
        {"landscape_upside_down", Rotation::landscape_upside_down},
        {"portrait_upside_down", Rotation::portrait_upside_down}
    };

    void initialize(const char* executable_path) {
        setenv("VIPS_WARNING", "1", true);

        if (vips_init(executable_path)) {
            vips_error_exit(nullptr);
        }
    }

    void uninitalize() {
        vips_shutdown();
    }

    bool convert(const char* image_path, uint32_t width, const Palette& palette, const Options& options,
            std::span<uint8_t> output, Rotation* output_rotation) {
        if (!image_path) {
            std::cerr << "Image path is null" << std::endl;
            return false;
        }

        const uint32_t height = output.size() / width;
        if (height <= 0) {
            std::cerr << "Output buffer is too small" << std::endl;
            return false;
        }

        vips::VImage image;
        std::exception vips_load_error;
        try {
            image = vips::VImage::new_from_file(image_path);
        } catch (const std::exception& error) {
            vips_load_error = error;
        }

        try {
            if (image.is_null()) {
                // Image format might have been misidentified: explicitly retry with Magick.
                image = vips::VImage::magickload(image_path);
            }
        } catch (const std::exception& magick_error) {
            std::cerr << "VIPS load error: " << vips_load_error.what() << std::endl;
            std::cerr << "Magick load error: " << magick_error.what() << std::endl;
            return false;
        }

        try {
            image = image.icc_import(vips::VImage::option()->set("pcs", VipsPCS::VIPS_PCS_XYZ)->
                set("intent", VipsIntent::VIPS_INTENT_PERCEPTUAL)->set("embedded", true));

            image = xyz_to_oklab(image);

            auto fill_color = oklab_black;
            if (image.has_alpha()) {
                image = image.flatten(vips::VImage::option()->set("background", fill_color));
            }

            image = image.autorot();

            auto computed_rotation = options.rotation;
            if (computed_rotation == Rotation::automatic && image.height() > image.width()) {
                computed_rotation = Rotation::portrait;
            }

            if (output_rotation) {
                *output_rotation = computed_rotation;
            }

            switch (computed_rotation) {
                case Rotation::automatic:
                case Rotation::landscape:
                default:
                    break;
                case Rotation::portrait:
                    image = image.rot270();
                    break;
                case Rotation::portrait_upside_down:
                    image = image.rot90();
                    break;
                case Rotation::landscape_upside_down:
                    image = image.rot180();
                    break;
            }

            const auto horizontal_scale = static_cast<double>(width) / image.width();
            const auto vertical_scale = static_cast<double>(height) / image.height();
            image = image.resize(std::min(horizontal_scale, vertical_scale));

            image = adjust_lightness(image, palette, options.dynamic_range, options.exposure,
                    options.brightness, options.contrast);

            image = image.sharpen(vips::VImage::option()->set("y2", 5)->set("y3", 5)->
                    set("m1", options.sharpening)->set("m2", options.sharpening));

            image = image.gravity(VipsCompassDirection::VIPS_COMPASS_DIRECTION_CENTRE, width, height,
                vips::VImage::option()->set("extend", VipsExtend::VIPS_EXTEND_BACKGROUND)->set("background", fill_color));

            dither(image, palette, options.clipped_chroma_recovery, options.error_attenuation, output);
        } catch (const std::exception& error) {
            std::cerr << "Error: \"" << error.what() << "\"" << std::endl;
            return false;
        }

        return true;
    }

    bool write_preview(std::span<const uint8_t> converted, uint32_t width, std::span<const Oklab> palette_points,
            const Rotation& output_rotation, const char* image_path) {
        if (!image_path) {
            std::cerr << "Image path is null" << std::endl;
            return false;
        }

        const uint32_t height = converted.size() / width;
        if (height <= 0) {
            std::cerr << "Input buffer is too small" << std::endl;
            return false;
        }

        vips::VImage image;
        try {
            // Underlying C API actually takes `const void *data`, cast is safe
            auto indices = vips::VImage::new_from_memory(const_cast<uint8_t*>(converted.data()), converted.size_bytes(),
                    width, height, 1, VIPS_FORMAT_UCHAR);
            auto lut = vips::VImage::new_from_memory(const_cast<Oklab*>(palette_points.data()), palette_points.size_bytes(),
                    palette_points.size(), 1, 3, VIPS_FORMAT_FLOAT);
            image = indices.maplut(lut);

            // Undo rotation
            switch (output_rotation)
            {
            case Rotation::automatic:
            case Rotation::landscape:
            default:
                break;
            case Rotation::portrait:
                image = image.rot90();
                break;
            case Rotation::portrait_upside_down:
                image = image.rot270();
                break;
            case Rotation::landscape_upside_down:
                image = image.rot180();
                break;
            }

            image = oklab_to_xyz(image);
            image.write_to_file(image_path);
        } catch (const std::exception& error) {
            std::cerr << "Error: \"" << error.what() << "\"" << std::endl;
            return false;
        }

        return true;
    }
}
