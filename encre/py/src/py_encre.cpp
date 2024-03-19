#include <encre.hpp>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

namespace py = pybind11;

PYBIND11_MODULE(py_encre, m) {
    m.doc() = "Python bindings for Encre";

    py::class_<encre::CIEXYZ>(m, "CIEXYZ").
        def(py::init<float, float, float>()).
        def_readwrite("x", &encre::CIEXYZ::x).
        def_readwrite("y", &encre::CIEXYZ::y).
        def_readwrite("z", &encre::CIEXYZ::z);

    py::class_<encre::CIELab>(m, "CIELab").
        def(py::init<float, float, float>()).
        def_readwrite("l", &encre::CIELab::x).
        def_readwrite("a", &encre::CIELab::y).
        def_readwrite("b", &encre::CIELab::z);

    py::class_<encre::Oklab>(m, "Oklab").
        def(py::init<float, float, float>()).
        def_readwrite("l", &encre::Oklab::x).
        def_readwrite("a", &encre::Oklab::y).
        def_readwrite("b", &encre::Oklab::z);

    py::class_<encre::Plane>(m, "Plane").
        def(py::init<float, float, float, float>()).
        def_readwrite("a", &encre::Plane::x).
        def_readwrite("b", &encre::Plane::y).
        def_readwrite("c", &encre::Plane::z).
        def_readwrite("d", &encre::Plane::w);

    py::class_<encre::Palette>(m, "Palette").
        def_readonly_static("default_target_luminance", &encre::Palette::default_target_luminance).
        def_readwrite("elements", &encre::Palette::elements).
        def_readwrite("gamut_hull", &encre::Palette::gamut_hull).
        def_readwrite("gray_line", &encre::Palette::gray_line);

    py::enum_<encre::Rotation>(m, "Rotation").
        value("automatic", encre::Rotation::automatic).
        value("landscape", encre::Rotation::landscape).
        value("portrait", encre::Rotation::portrait).
        value("landscape_upside_down", encre::Rotation::landscape_upside_down).
        value("portrait_upside_down", encre::Rotation::portrait_upside_down);

    py::class_<encre::Options>(m, "Options").
        def(py::init()).
        def_readonly_static("default_rotation", &encre::Options::default_rotation).
        def_readonly_static("default_contrast_coverage_percent", &encre::Options::default_contrast_coverage_percent).
        def_readonly_static("default_contrast_compression", &encre::Options::default_contrast_compression).
        def_readonly_static("default_clipped_gamut_recovery", &encre::Options::default_clipped_gamut_recovery).
        def_readwrite("rotation", &encre::Options::rotation).
        def_readwrite("contrast_coverage_percent", &encre::Options::contrast_coverage_percent).
        def_readwrite("contrast_compression", &encre::Options::contrast_compression).
        def_readwrite("clipped_gamut_recovery", &encre::Options::clipped_gamut_recovery);

    m.attr("waveshare_7dot3_inch_e_paper_f_palette") = encre::waveshare_7dot3_inch_e_paper_f_palette;

    m.def("initialize", &encre::initialize, py::arg("executable_path"), "Initialize the runtime");
    m.def("uninitalize", &encre::uninitalize, "Un-initialize the runtime");

    m.def("make_palette_xyz", [](const std::vector<encre::CIEXYZ>& colors, float target_luminance) {
                return encre::make_palette(colors, target_luminance);
            }, py::arg("colors"), py::arg("target_luminance") = encre::Palette::default_target_luminance, "Make a palette from CIE XYZ colors");
    m.def("make_palette_lab", [](const std::vector<encre::CIELab>& colors, float target_luminance) {
                return encre::make_palette(colors, target_luminance);
            }, py::arg("colors"), py::arg("target_luminance") = encre::Palette::default_target_luminance, "Make a palette from CIE Lab colors");

    m.def("convert", [](const char* image_path, const encre::Palette& palette, py::array_t<uint8_t> output,
                        const encre::Options& options, const char* dithered_image_path) {
                auto mutable_output = output.mutable_unchecked<2>();
                const std::span<uint8_t> output_span{mutable_output.mutable_data(0, 0), static_cast<size_t>(mutable_output.size())};
                return encre::convert(image_path, static_cast<uint32_t>(mutable_output.shape(1)), static_cast<uint32_t>(mutable_output.shape(0)),
                        palette, options, output_span, dithered_image_path);
            },
            py::arg("image_path"), py::arg("palette"), py::arg("output").noconvert(), py::kw_only(),
            py::arg("options") = encre::Options{}, py::arg("dithered_image_path") = nullptr, "Convert an image to the palette");
}
