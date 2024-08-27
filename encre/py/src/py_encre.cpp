#include <encre.hpp>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include <string_view>
#include <optional>

namespace py = pybind11;

namespace {
    template<typename T>
    std::optional<T> try_get(const py::object& object, const char* name) {
        if (!object.contains(name)) {
            return std::nullopt;
        }

        return object[name].cast<T>();
    }

    template<typename T, typename S = T>
    const auto read_option(const py::object& object, const char* name, T& storage) {
        if (const auto value = try_get<float>(object, name))
            storage = *value;
    }

    template<typename T>
    const auto read_option(const py::object& object, const char* name, std::optional<T>& storage) {
        read_option<std::optional<T>, T>(object, name, storage);
    }
}

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
        def_readonly_static("default_target_lightness", &encre::Palette::default_target_lightness).
        def_readwrite("points", &encre::Palette::points).
        def_readwrite("gamut_vertices", &encre::Palette::gamut_vertices).
        def_readwrite("gamut_planes", &encre::Palette::gamut_planes).
        def_readwrite("gray_line", &encre::Palette::gray_line).
        def_readwrite("lightness_range", &encre::Palette::lightness_range).
        def_readwrite("max_chroma", &encre::Palette::max_chroma);

    py::enum_<encre::Rotation>(m, "Rotation").
        value("automatic", encre::Rotation::automatic).
        value("landscape", encre::Rotation::landscape).
        value("portrait", encre::Rotation::portrait).
        value("landscape_upside_down", encre::Rotation::landscape_upside_down).
        value("portrait_upside_down", encre::Rotation::portrait_upside_down);

    m.attr("rotation_by_name") = encre::rotation_by_name;

    py::class_<encre::Options>(m, "Options").
        def(py::init([](const py::kwargs& arguments) {
            encre::Options options{};
            if (const auto value = try_get<std::string>(arguments, "rotation"))
                options.rotation = encre::rotation_by_name.at(*value);
            read_option(arguments, "dynamic_range", options.dynamic_range);
            read_option(arguments, "exposure", options.exposure);
            read_option(arguments, "brightness", options.brightness);
            read_option(arguments, "contrast", options.contrast);
            read_option(arguments, "sharpening", options.sharpening);
            read_option(arguments, "clipped_chroma_recovery", options.clipped_chroma_recovery);
            read_option(arguments, "error_attenuation", options.error_attenuation);
            return options;
        })).
        def_readonly_static("default_rotation", &encre::Options::default_rotation).
        def_readonly_static("default_dynamic_range", &encre::Options::default_dynamic_range).
        def_readonly_static("automatic_brightness", &encre::Options::automatic_brightness).
        def_readonly_static("automatic_exposure", &encre::Options::automatic_exposure).
        def_readonly_static("no_exposure_change", &encre::Options::no_exposure_change).
        def_readonly_static("no_brightness_change", &encre::Options::no_brightness_change).
        def_readonly_static("default_contrast", &encre::Options::default_contrast).
        def_readonly_static("default_sharpening", &encre::Options::default_sharpening).
        def_readonly_static("default_clipped_chroma_recovery", &encre::Options::default_clipped_chroma_recovery).
        def_readonly_static("default_error_attenuation", &encre::Options::default_error_attenuation).
        def_readwrite("rotation", &encre::Options::rotation).
        def_readwrite("dynamic_range", &encre::Options::dynamic_range).
        def_readwrite("exposure", &encre::Options::exposure).
        def_readwrite("brightness", &encre::Options::brightness).
        def_readwrite("contrast", &encre::Options::contrast).
        def_readwrite("sharpening", &encre::Options::sharpening).
        def_readwrite("clipped_chroma_recovery", &encre::Options::clipped_chroma_recovery).
        def_readwrite("error_attenuation", &encre::Options::error_attenuation);

    m.attr("waveshare_gallery_palette_palette") = encre::waveshare_gallery_palette_palette;
    m.attr("pimoroni_gallery_palette_palette") = encre::pimoroni_gallery_palette_palette;
    m.attr("GDEP073E01_spectra_6_palette") = encre::GDEP073E01_spectra_6_palette;

    m.attr("palette_by_name") = encre::palette_by_name;

    m.def("initialize", &encre::initialize, py::arg("executable_path"), "Initialize the runtime");
    m.def("uninitalize", &encre::uninitalize, "Un-initialize the runtime");

    m.def("make_palette_xyz", [](const std::vector<encre::CIEXYZ>& colors, float target_lightness) {
                return encre::make_palette(colors, target_lightness);
            }, py::arg("colors"), py::arg("target_lightness") = encre::Palette::default_target_lightness, "Make a palette from CIE XYZ colors");
    m.def("make_palette_lab", [](const std::vector<encre::CIELab>& colors, float target_lightness) {
                return encre::make_palette(colors, target_lightness);
            }, py::arg("colors"), py::arg("target_lightness") = encre::Palette::default_target_lightness, "Make a palette from CIE Lab colors");

    m.def("convert", [](const char* image_path, const encre::Palette& palette, py::array_t<uint8_t> output,
                        const encre::Options& options, const char* preview_image_path) {
                auto mutable_output = output.mutable_unchecked<2>();
                const std::span<uint8_t> output_span{mutable_output.mutable_data(0, 0), static_cast<size_t>(mutable_output.size())};
                return encre::convert(image_path, static_cast<uint32_t>(mutable_output.shape(1)), static_cast<uint32_t>(mutable_output.shape(0)),
                        palette, options, output_span, preview_image_path);
            },
            py::arg("image_path"), py::arg("palette"), py::arg("output").noconvert(), py::kw_only(),
            py::arg("options") = encre::Options{}, py::arg("preview_image_path") = static_cast<const char*>(nullptr), "Convert an image to the palette");
}
