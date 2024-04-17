#include "encre.hpp"

#include "oklab.hpp"

#include <libqhullcpp/Qhull.h>
#include <libqhullcpp/QhullFacetList.h>
#include <libqhullcpp/QhullRidge.h>

#include <vips/vips8>

#ifdef PRINT_HULL
#include <iostream>
#endif

namespace encre {
    const Palette waveshare_7_color_palette = make_palette(
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

    const Palette inky_7_color_palette = make_palette(
        std::to_array<CIELab>({
            {15.45f, 5.08f, -8.48f},
            {73.65f, -1.01f, 2.65f},
            {42.76f, -31.94f, 16.43f},
            {28.f, 9.2f, -25.f},
            {49.02f, 35.9f, 17.4f},
            {68.38f, -4.95f, 56.42f},
            {55.04f, 24.9f, 30.f},
        })
    );

    // Using std::map to keep the name ordering consistent
    const std::map<std::string, const Palette*> palette_by_name{
        {"waveshare_7_color", &waveshare_7_color_palette},
        {"inky_7_color", &inky_7_color_palette},
    };

    Palette make_palette(std::span<const CIEXYZ> colors, float target_luminance) {
        std::vector<Oklab> gamut_vertices;
        gamut_vertices.reserve(colors.size());

        for (const auto xyz : colors) {
            gamut_vertices.push_back(xyz_to_oklab(xyz));
        }

        const auto gamut_vertex_count = gamut_vertices.size();

        const auto max_l = std::max_element(gamut_vertices.begin(), gamut_vertices.end(),
            [](const auto& a, const auto& b) { return a.x < b.x; })->x;
        const auto l_scale = target_luminance / max_l;
        for (auto& lab : gamut_vertices) {
            lab.x *= l_scale;
        }

        std::vector<double> gamut_vertices_qhull;
        gamut_vertices_qhull.reserve(gamut_vertex_count * 3);
        for (const auto lab : gamut_vertices) {
            gamut_vertices_qhull.push_back(lab.x);
            gamut_vertices_qhull.push_back(lab.y);
            gamut_vertices_qhull.push_back(lab.z);
        }

        const auto hull = orgQhull::Qhull("", 3, static_cast<int>(gamut_vertex_count), gamut_vertices_qhull.data(), "Qt");

        #ifdef PRINT_HULL
        std::cout << "const int palette_hull_facet_count = " << hull.facetCount() << ";\n";
        std::cout << "const vec4[palette_hull_facet_count] palette_hull = vec4[palette_hull_facet_count](\n";
        #endif

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

            #ifdef PRINT_HULL
            std::cout << "    vec4(" << coordinates[0] << ", " << coordinates[1] << ", " <<
                    coordinates[2] << ", " << plane.offset() / 100 << ")";
            if (gamut_planes.size() < hull.facetCount()) {
                std::cout << ",";
            }
            std::cout << "\n";
            #endif
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

        #ifdef PRINT_HULL
        std::cout << ");\n";
        std::cout << "const vec2 gray_line = vec2(" << min_gray_l / 100 << ", " << max_gray_l / 100 << ");\n\n";
        #endif

        return {std::move(gamut_vertices), std::move(gamut_planes), {min_gray_l, max_gray_l}};
    }

    Palette make_palette(std::span<const CIELab> lab_colors, float target_luminance) {
        std::vector<CIEXYZ> xyz_colors;
        xyz_colors.reserve(lab_colors.size());

        for (const auto lab : lab_colors) {
            auto& xyz = xyz_colors.emplace_back();
            vips_col_Lab2XYZ(lab.x, lab.y, lab.z, &xyz.x, &xyz.y, &xyz.z);
        }

        return make_palette(xyz_colors, target_luminance);
    }
}
