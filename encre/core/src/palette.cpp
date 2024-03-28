#include "encre.hpp"

#include "oklab.hpp"

#include <libqhullcpp/Qhull.h>
#include <libqhullcpp/QhullFacetList.h>
#include <libqhullcpp/QhullRidge.h>

#include <vips/vips8>

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

        const auto hull = orgQhull::Qhull("", 3, static_cast<int>(gamut_vertex_count), gamut_vertices_qhull.data(), "");

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
