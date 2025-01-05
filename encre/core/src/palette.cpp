#include "encre.hpp"

#include "oklab.hpp"

#include <libqhullcpp/Qhull.h>
#include <libqhullcpp/QhullFacetList.h>
#include <libqhullcpp/QhullRidge.h>

#include <vips/vips8>

#define GLM_ENABLE_EXPERIMENTAL
#include <glm/gtx/vec_swizzle.hpp>

#include <unordered_map>

#ifdef PRINT_HULL
#include <iostream>
#endif

namespace encre {
    const Palette eink_gallery_palette_palette = make_palette(
        std::to_array<CIELab>({
            {15.45f, 5.08f, -8.48f}, // Black
            {73.65f, -1.01f, 2.65f}, // White
            {42.76f, -31.94f, 16.43f}, // Green
            {28.f, 9.2f, -25.f}, // Blue
            {49.02f, 35.9f, 17.4f}, // Red
            {68.38f, -4.95f, 56.42f}, // Yellow
            {55.04f, 24.9f, 30.f}, // Orange
        })
    );

    const Palette eink_spectra_6_palette = make_palette(
        std::to_array<CIELab>({
            {21.60f, 4.86f, -8.00f}, // Black
            {90.25f, -0.99f, 2.05f}, // White
            {84.43f, -3.30f, 74.66f}, // Yellow
            {37.85f, 43.36f, 29.41f}, // Red
            {45.22f, 14.33f, -53.44f}, // Blue
            {51.25f, -24.45f, 21.48f}, // Green
        })
    );

    // Using std::map to keep the name ordering consistent
    const std::map<std::string, Palette> palette_by_name{
        {"eink_gallery_palette", eink_gallery_palette_palette},
        {"eink_spectra_6", eink_spectra_6_palette},
    };

    Palette make_palette(std::span<const CIEXYZ> colors, float target_lightness) {
        const auto point_count = colors.size();

        glm::vec2 l_extents{std::numeric_limits<float>::max(), std::numeric_limits<float>::lowest()};
        float c_max = 0;

        std::vector<Oklab> points;
        points.reserve(point_count);
        std::vector<double> points_flattened;
        points_flattened.reserve(point_count * 3);
        for (const auto xyz : colors) {
            const auto lab = xyz_to_oklab(xyz);

            points.push_back(lab);
            points_flattened.push_back(lab.x);
            points_flattened.push_back(lab.y);
            points_flattened.push_back(lab.z);

            if (lab.x < l_extents.x) {
                l_extents.x = lab.x;
            } else if (lab.x > l_extents.y) {
                l_extents.y = lab.x;
            }

            const auto c = glm::length(glm::yz(lab));
            if (c > c_max) {
                c_max = c;
            }
        }

        const auto l_scale = target_lightness / l_extents.y;
        l_extents = {l_extents.x * l_scale, target_lightness};
        for (size_t i = 0; i < point_count; i++) {
            points[i].x *= l_scale;
            points_flattened[i * 3] *= l_scale;
        }

        const auto hull = orgQhull::Qhull("", 3, static_cast<int>(point_count), points_flattened.data(), "Qt");

        std::vector<Oklab> gamut_vertices;
        gamut_vertices.reserve(hull.vertexCount());
        for (const auto& vertex : hull.vertexList()) {
            const auto coordinates = vertex.point().coordinates();
            gamut_vertices.push_back(Oklab{
                static_cast<float>(coordinates[0]),
                static_cast<float>(coordinates[1]),
                static_cast<float>(coordinates[2])});
        }

        const auto edge_count = hull.facetCount() + hull.vertexCount() - 2; // Euler's formula
        #ifdef PRINT_HULL
        std::cout << "const int palette_edge_count = " << edge_count << ";\n";
        std::cout << "const mat2x3[palette_edge_count] palette_edges = mat2x3[palette_edge_count](\n";
        #endif

        std::unordered_map<countT, Edge> gamut_edges_by_id;
        gamut_edges_by_id.reserve(edge_count);
        for (const auto& facet : hull.facetList()) {
            qh_makeridges(hull.qh(), facet.getFacetT());
            for (const auto& ridge : facet.ridges()) {
                if (gamut_edges_by_id.contains(ridge.id())) {
                    continue;
                }

                const auto& vertices = ridge.vertices();
                const auto start_coordinates = vertices.first().point().coordinates();
                const auto end_coordinates = vertices.last().point().coordinates();
                const Edge edge{
                    {
                        static_cast<float>(start_coordinates[0]),
                        static_cast<float>(start_coordinates[1]),
                        static_cast<float>(start_coordinates[2])
                    },
                    {
                        static_cast<float>(end_coordinates[0]),
                        static_cast<float>(end_coordinates[1]),
                        static_cast<float>(end_coordinates[2])
                    }
                };
                gamut_edges_by_id[ridge.id()] = edge;

                #ifdef PRINT_HULL
                std::cout << "    mat2x3(vec3(" << edge[0][0] << ", " << edge[0][1] << ", " << edge[0][2] << ")," <<
                        " vec3(" << edge[1][0] << ", " << edge[1][1] << ", " << edge[1][2] << "))";
                if (gamut_edges.size() < edge_count) {
                    std::cout << ",";
                }
                std::cout << "\n";
                #endif
            }
        }

        std::vector<Edge> gamut_edges;
        gamut_edges.reserve(edge_count);
        for (const auto& [_, edge] : gamut_edges_by_id) {
            gamut_edges.push_back(edge);
        }

        #ifdef PRINT_HULL
        std::cout << ");\n";
        std::cout << "const int palette_facet_count = " << hull.facetCount() << ";\n";
        std::cout << "const vec4[palette_facet_count] palette_facets = vec4[palette_facet_count](\n";
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
        std::cout << "const vec2 gray_range = vec2(" << min_gray_l / 100 << ", " << max_gray_l / 100 << ");\n\n";
        #endif

        return {
            .points = std::move(points),
            .gamut_vertices = std::move(gamut_vertices),
            .gamut_edges = std::move(gamut_edges),
            .gamut_planes = std::move(gamut_planes),
            .gray_range = {min_gray_l, max_gray_l},
            .lightness_range = l_extents.y - l_extents.x,
            .max_chroma = c_max
        };
    }

    Palette make_palette(std::span<const CIELab> lab_colors, float target_lightness) {
        std::vector<CIEXYZ> xyz_colors;
        xyz_colors.reserve(lab_colors.size());

        for (const auto lab : lab_colors) {
            auto& xyz = xyz_colors.emplace_back();
            vips_col_Lab2XYZ(lab.x, lab.y, lab.z, &xyz.x, &xyz.y, &xyz.z);
        }

        return make_palette(xyz_colors, target_lightness);
    }
}
