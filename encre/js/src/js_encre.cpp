#include <encre.hpp>

#include <emscripten/emscripten.h>
#include <emscripten/bind.h>

namespace em = emscripten;

EMSCRIPTEN_BINDINGS(js_encre) {
    em::value_object<encre::CIEXYZ>("CIEXYZ").
        field("x", &encre::CIEXYZ::x).
        field("y", &encre::CIEXYZ::y).
        field("z", &encre::CIEXYZ::z);

    em::value_object<encre::CIELab>("CIELab").
        field("l", &encre::CIELab::x).
        field("a", &encre::CIELab::y).
        field("b", &encre::CIELab::z);

    em::value_object<encre::Oklab>("Oklab").
        field("l", &encre::Oklab::x).
        field("a", &encre::Oklab::y).
        field("b", &encre::Oklab::z);

    em::value_object<encre::Plane>("Plane").
        field("a", &encre::Plane::x).
        field("b", &encre::Plane::y).
        field("c", &encre::Plane::z).
        field("d", &encre::Plane::w);

    em::value_object<encre::Line>("Line").
        field("x", &encre::Line::x).
        field("y", &encre::Line::y);

    em::register_vector<encre::Oklab>("OklabArray");
    em::register_vector<encre::Plane>("PlaneArray");

    em::constant("default_target_lightness", encre::Palette::default_target_lightness);
    em::value_object<encre::Palette>("Palette").
        field("points", &encre::Palette::points).
        field("gamut_vertices", &encre::Palette::gamut_vertices).
        field("gamut_planes", &encre::Palette::gamut_planes).
        field("gray_line", &encre::Palette::gray_line).
        field("lightness_range", &encre::Palette::lightness_range).
        field("max_chroma", &encre::Palette::max_chroma);

    em::enum_<encre::Rotation>("Rotation").
        value("automatic", encre::Rotation::automatic).
        value("landscape", encre::Rotation::landscape).
        value("portrait", encre::Rotation::portrait).
        value("landscape_upside_down", encre::Rotation::landscape_upside_down).
        value("portrait_upside_down", encre::Rotation::portrait_upside_down);

    em::register_map<std::string, encre::Rotation>("RotationNameMap");
    // em::constant("rotation_by_name", encre::rotation_by_name);

    em::register_optional<float>();

    em::constant("default_rotation", &encre::Options::default_rotation);
    em::constant("default_dynamic_range", &encre::Options::default_dynamic_range);
    em::constant("automatic_brightness", &encre::Options::automatic_brightness);
    em::constant("automatic_exposure", &encre::Options::automatic_exposure);
    em::constant("no_exposure_change", &encre::Options::no_exposure_change);
    em::constant("no_brightness_change", &encre::Options::no_brightness_change);
    em::constant("default_contrast", &encre::Options::default_contrast);
    em::constant("default_sharpening", &encre::Options::default_sharpening);
    em::constant("default_clipped_chroma_recovery", &encre::Options::default_clipped_chroma_recovery);
    em::constant("default_error_attenuation", &encre::Options::default_error_attenuation);
    em::value_object<encre::Options>("Options").
        field("rotation", &encre::Options::rotation).
        field("dynamic_range", &encre::Options::dynamic_range).
        field("exposure", &encre::Options::exposure).
        field("brightness", &encre::Options::brightness).
        field("contrast", &encre::Options::contrast).
        field("sharpening", &encre::Options::sharpening).
        field("clipped_chroma_recovery", &encre::Options::clipped_chroma_recovery).
        field("error_attenuation", &encre::Options::error_attenuation);

    em::constant("waveshare_gallery_palette_palette", encre::waveshare_gallery_palette_palette);
    em::constant("pimoroni_gallery_palette_palette", encre::pimoroni_gallery_palette_palette);
    em::constant("GDEP073E01_spectra_6_palette", encre::GDEP073E01_spectra_6_palette);

    // m.attr("palette_by_name") = encre::palette_by_name;

    // m.def("initialize", &encre::initialize, em::arg("executable_path"), "Initialize the runtime");
    // m.def("uninitalize", &encre::uninitalize, "Un-initialize the runtime");

    // m.def("make_palette_xyz", [](const std::vector<encre::CIEXYZ>& colors, float target_lightness) {
    //             return encre::make_palette(colors, target_lightness);
    //         }, em::arg("colors"), em::arg("target_lightness") = encre::Palette::default_target_lightness, "Make a palette from CIE XYZ colors");
    // m.def("make_palette_lab", [](const std::vector<encre::CIELab>& colors, float target_lightness) {
    //             return encre::make_palette(colors, target_lightness);
    //         }, em::arg("colors"), em::arg("target_lightness") = encre::Palette::default_target_lightness, "Make a palette from CIE Lab colors");

    // m.def("convert", [](const char* image_path, const encre::Palette& palette, em::array_t<uint8_t> output,
    //                     const encre::Options& options, const char* preview_image_path) {
    //             auto mutable_output = output.mutable_unchecked<2>();
    //             const std::span<uint8_t> output_span{mutable_output.mutable_data(0, 0), static_cast<size_t>(mutable_output.size())};
    //             return encre::convert(image_path, static_cast<uint32_t>(mutable_output.shape(1)), static_cast<uint32_t>(mutable_output.shape(0)),
    //                     palette, options, output_span, preview_image_path);
    //         },
    //         em::arg("image_path"), em::arg("palette"), em::arg("output").noconvert(), em::kw_only(),
    //         em::arg("options") = encre::Options{}, em::arg("preview_image_path") = static_cast<const char*>(nullptr), "Convert an image to the palette");
}
