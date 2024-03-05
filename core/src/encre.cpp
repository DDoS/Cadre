#include "encre.hpp"

#include "oklab.hpp"
#include "dither.hpp"

#include <vips/vips8>

#include <libqhullcpp/Qhull.h>
#include <libqhullcpp/QhullFacetList.h>
#include <libqhullcpp/QhullRidge.h>

#include <iostream>
#include <unordered_map>
#include <functional>

namespace std {
    template<typename T1, typename T2>
    struct hash<std::pair<T1, T2>> {
        std::size_t operator()(const std::pair<T1, T2>& p) const {
            return std::hash<T1>{}(p.first) ^ std::hash<T2>{}(p.second);
        }
    };
}

namespace encre {
    // From Waveshare 7.3inch e-Paper (F) datasheet section 8-1
    const Palette waveshare_7dot3_inch_e_paper_f_palette = make_palette(
        std::to_array<CIELab>({
            {17.6f, 8.3f, -8.9f},
            {70.6f, -0.4f, 2.4f},
            {38.3f, -26.0f, 13.4f},
            {28.0f, 9.2f, -25.0f},
            {37.6f, 35.9f, 17.4f},
            {65.5f, -6.7f, 46.4f},
            {44.4f, 24.9f, 30.0f}, // Orange "a" and "b" were swapped?
        })
    );

    void initialize(const char* executable_path) {
        if (VIPS_INIT(executable_path))
            vips_error_exit(nullptr);
    }

    void uninitalize() {
        vips_shutdown();
    }

    Palette make_palette(std::span<const CIEXYZ> colors, float target_luminance) {
        std::vector<Oklab> oklab_elements;
        oklab_elements.reserve(colors.size());

        for (const auto xyz : colors) {
            oklab_elements.push_back(xyz_to_oklab(xyz));
        }

        const auto max_l = std::max_element(oklab_elements.begin(), oklab_elements.end(),
            [](const auto& a, const auto& b) { return a.x < b.x; })->x;
        const auto l_scale = target_luminance / max_l;
        for (auto& lab : oklab_elements) {
            lab.x *= l_scale;
        }

        std::vector<double> points;
        const auto point_count = oklab_elements.size();
        points.reserve(point_count * 3);
        for (const auto lab : oklab_elements) {
            points.push_back(lab.x);
            points.push_back(lab.y);
            points.push_back(lab.z);
        }

        const auto hull = orgQhull::Qhull("", 3, static_cast<int>(point_count), points.data(), "");

        std::vector<Plane> gamut_planes;
        gamut_planes.reserve(hull.facetCount());
        for (const auto& facet : hull.facetList()) {
            const auto plane = facet.hyperplane();
            const auto coordinates = plane.coordinates();
            gamut_planes.push_back(Plane{
                static_cast<float>(coordinates[0]),
                static_cast<float>(coordinates[1]),
                static_cast<float>(coordinates[2]),
                static_cast<float>(plane.offset())});
        }

        auto max_gray_l = std::numeric_limits<float>::max(), min_gray_l = std::numeric_limits<float>::min();
        for (const auto& plane : gamut_planes) {
            const float l = -plane.w / plane.x;
            if (plane.x < 0) {
                min_gray_l = std::max(min_gray_l, l);
            } else {
                max_gray_l = std::min(max_gray_l, l);
            }
        }

        return {std::move(oklab_elements), std::move(gamut_planes), {min_gray_l, max_gray_l}};
    }

    Palette make_palette(std::span<const CIELab> colors, float target_luminance) {
        std::vector<CIEXYZ> xyz_elements;
        xyz_elements.reserve(colors.size());

        for (const auto lab : colors) {
            auto& xyz = xyz_elements.emplace_back();
            vips_col_Lab2XYZ(lab.x, lab.y, lab.z, &xyz.x, &xyz.y, &xyz.z);
        }

        return make_palette(xyz_elements, target_luminance);
    }

    bool convert(const char* image_path, uint32_t width, uint32_t height, const Palette& palette,
            std::span<uint8_t> output, const char* dithered_image_path, float lightness_adaptation_factor) {

        if (output.size() < width * height) {
            std::cerr << "Output buffer is too small\n";
            return false;
        }

        try {
            auto image = vips::VImage::new_from_file(image_path, vips::VImage::option()->
                set("access", VIPS_ACCESS_SEQUENTIAL)->set("autorotate", true));
            image = image.icc_import(vips::VImage::option()->set("pcs", VipsPCS::VIPS_PCS_XYZ)->
                set("intent", VipsIntent::VIPS_INTENT_PERCEPTUAL)->set("embedded", true));

            image = encre::xyz_to_oklab(image);

            static const std::vector<double> oklab_white{100, 0, 0};
            if (image.has_alpha()) {
                image = image.flatten(vips::VImage::option()->set("background", oklab_white));
            }

            const auto horizontal_scale = static_cast<double>(width) / image.width();
            const auto vertical_scale = static_cast<double>(height) / image.height();
            image = image.resize(std::min(horizontal_scale, vertical_scale));

            image = image.gravity(VipsCompassDirection::VIPS_COMPASS_DIRECTION_CENTRE, width, height,
                vips::VImage::option()->set("extend", VipsExtend::VIPS_EXTEND_BACKGROUND)->set("background", oklab_white));

            encre::dither(image, palette, lightness_adaptation_factor, output);

            if (dithered_image_path) {
                image = encre::oklab_to_xyz(image);
                image.write_to_file(dithered_image_path);
            }

            return true;
        } catch (const vips::VError& error) {
            error.ostream_print(std::cerr);
            return false;
        }
    }
}
