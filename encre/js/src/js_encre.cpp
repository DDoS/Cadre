#include <encre.hpp>

#include <emscripten/emscripten.h>
#include <emscripten/bind.h>

#include <type_traits>
#include <span>

namespace em = emscripten;

template<typename Lambda>
static auto lambda_to_ptr(Lambda&& function) ->
        em::internal::remove_class<decltype(&Lambda::operator())>::type* {
    return function;
}

static size_t get_typed_array_size(const em::val& typed_array) {
    const auto bytes_per_element = typed_array["BYTES_PER_ELEMENT"].as<size_t>();
    const auto length = typed_array["length"].as<size_t>();
    return length * bytes_per_element;
}

enum ReadWrite {
    read,
    write
};

template<ReadWrite readWrite, typename T>
static void readwrite_typed_array(const std::vector<T>& vector, const em::val& typed_array) {
    const auto byte_offset = reinterpret_cast<uintptr_t>(vector.data());
    const auto length = typed_array["length"].as<size_t>();
    em::val buffer = em::val::module_property("HEAPU8")["buffer"];
    em::val vector_typed_array = typed_array["constructor"].new_(buffer, byte_offset, length);
    if constexpr (readWrite == read) {
        vector_typed_array.call<void>("set", typed_array);
    } else {
        typed_array.call<void>("set", vector_typed_array);
    }
}

static std::optional<encre::Rotation> bind_convert(const std::string& image_path, uint32_t width,
        const encre::Palette& palette, const encre::Options& options, em::val output) {
    std::vector<uint8_t> output_buffer(get_typed_array_size(output));
    encre::Rotation output_rotation{};
    if (!encre::convert(image_path.c_str(), width, palette, options,
            output_buffer, &output_rotation)) {
        return std::nullopt;
    }

    readwrite_typed_array<write>(output_buffer, output);
    return output_rotation;
}

static bool bind_write_preview(em::val converted, uint32_t width, const std::vector<encre::Oklab>& palette_points,
        const encre::Rotation& output_rotation, const std::string& image_path) {
    std::vector<uint8_t> input_buffer(get_typed_array_size(converted));
    readwrite_typed_array<read>(input_buffer, converted);
    return encre::write_preview(input_buffer, width,
            palette_points, output_rotation, image_path.c_str());
}

static bool bind_write_encre_file(em::val converted, uint32_t width, const std::vector<encre::Oklab>& palette_points,
        const encre::Rotation& output_rotation, const std::string& image_path) {
    std::vector<uint8_t> input_buffer(get_typed_array_size(converted));
    readwrite_typed_array<read>(input_buffer, converted);
    return encre::write_encre_file(input_buffer, width,
            palette_points, output_rotation, image_path.c_str());
}

static std::optional<std::pair<uint32_t, encre::Rotation>> bind_read_encre_file(const std::string& image_path,
        em::val output, std::vector<encre::Oklab>& palette_points) {
    std::vector<uint8_t> output_buffer;
    uint32_t width;
    encre::Rotation output_rotation;
    if (!encre::read_encre_file(image_path.c_str(), output_buffer, width,
            palette_points, output_rotation)) {
        return std::nullopt;
    }

    readwrite_typed_array<write>(output_buffer, output);
    return std::make_pair(width, output_rotation);
}

static std::optional<encre::Rotation> bind_read_compatible_encre_file(const std::string& image_path, uint32_t width,
        size_t palette_size, em::val output) {
    std::vector<uint8_t> output_buffer(get_typed_array_size(output));
    encre::Rotation output_rotation{};
    if (!encre::read_compatible_encre_file(image_path.c_str(), width, palette_size,
            output_buffer, &output_rotation)) {
        return std::nullopt;
    }

    readwrite_typed_array<write>(output_buffer, output);
    return output_rotation;
}

EMSCRIPTEN_BINDINGS(js_encre) {
    em::register_vector<std::string>("StringArray");

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

    em::register_vector<encre::CIEXYZ>("CIEXYZArray");
    em::register_vector<encre::CIELab>("CIELabArray");
    em::register_vector<encre::Oklab>("OklabArray");
    em::register_vector<encre::Plane>("PlaneArray");

    em::constant("default_target_lightness", encre::Palette::default_target_lightness);

    em::class_<encre::Palette>("Palette").
        property("points", &encre::Palette::points).
        property("gamut_vertices", &encre::Palette::gamut_vertices).
        property("gamut_planes", &encre::Palette::gamut_planes).
        property("gray_line", &encre::Palette::gray_line).
        property("lightness_range", &encre::Palette::lightness_range).
        property("max_chroma", &encre::Palette::max_chroma);

    em::enum_<encre::Rotation>("Rotation").
        value("automatic", encre::Rotation::automatic).
        value("landscape", encre::Rotation::landscape).
        value("portrait", encre::Rotation::portrait).
        value("landscape_upside_down", encre::Rotation::landscape_upside_down).
        value("portrait_upside_down", encre::Rotation::portrait_upside_down);

    em::register_map<std::string, encre::Rotation>("RotationNameMap");
    em::function("rotation_by_name", lambda_to_ptr([] { return encre::rotation_by_name; }),
            em::return_value_policy::take_ownership());

    em::register_optional<float>();
    em::register_optional<encre::Rotation>();
    em::register_optional<std::pair<uint32_t, encre::Rotation>>();

    em::value_object<std::pair<uint32_t, encre::Rotation>>("WithAndRotation").
        field("width", &std::pair<uint32_t, encre::Rotation>::first).
        field("rotation", &std::pair<uint32_t, encre::Rotation>::second);

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
    em::function("default_options", lambda_to_ptr([] { return encre::Options{}; }));

    em::function("waveshare_gallery_palette_palette", lambda_to_ptr([] { return encre::waveshare_gallery_palette_palette; }), em::return_value_policy::take_ownership());
    em::function("pimoroni_gallery_palette_palette", lambda_to_ptr([] { return encre::pimoroni_gallery_palette_palette; }), em::return_value_policy::take_ownership());
    em::function("GDEP073E01_spectra_6_palette", lambda_to_ptr([] { return encre::GDEP073E01_spectra_6_palette; }), em::return_value_policy::take_ownership());

    em::register_map<std::string, encre::Palette>("PaletteNameMap");
    em::function("palette_by_name", lambda_to_ptr([] { return encre::palette_by_name; }), em::return_value_policy::take_ownership());

    em::function("initialize", lambda_to_ptr([] { encre::initialize("wasm-vips"); }));
    em::function("uninitalize", &encre::uninitalize);

    em::function("make_palette_xyz", lambda_to_ptr([](const std::vector<encre::CIEXYZ>& colors, float target_lightness) {
                return encre::make_palette(colors, target_lightness);
            }), em::return_value_policy::take_ownership());
    em::function("make_palette_lab", lambda_to_ptr([](const std::vector<encre::CIELab>& colors, float target_lightness) {
                return encre::make_palette(colors, target_lightness);
            }), em::return_value_policy::take_ownership());

    em::function("convert", &bind_convert);

    em::function("write_preview", &bind_write_preview);
    em::function("write_encre_file", &bind_write_encre_file);
    em::function("read_encre_file", &bind_read_encre_file);
    em::function("read_compatible_encre_file", &bind_read_compatible_encre_file);
}
