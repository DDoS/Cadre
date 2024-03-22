#include <encre.hpp>

#include <argparse/argparse.hpp>

#include <iostream>
#include <fstream>
#include <filesystem>

namespace {
    template<typename T, typename S = T>
    const auto read_option(const argparse::ArgumentParser& arguments, std::string_view name, T& storage) {
        if (const auto value = arguments.present<S>(name))
            storage = *value;
    }

    template<typename T>
    const auto read_option(const argparse::ArgumentParser& arguments, std::string_view name, std::optional<T>& storage) {
        read_option<std::optional<T>, T>(arguments, name, storage);
    }
}

int main(int arg_count, char** arg_values) {
    argparse::ArgumentParser arguments("encre-cli", "0.0.1");
    arguments.add_description("Command line interface for Encre");
    arguments.add_argument("input_image");
    arguments.add_argument("-w", "--width").scan<'u', uint32_t>().metavar("width").help("output width").default_value(800u);
    arguments.add_argument("-h", "--height").scan<'u', uint32_t>().metavar("height").help("output height").default_value(480u);
    arguments.add_argument("-o", "--out").metavar("output_binary").help("output binary").default_value("-");
    arguments.add_argument("-p", "--preview").metavar("output_preview_image").help("output preview image").default_value("-");
    arguments.add_argument("-v", "--dynamic-range").scan<'g', float>().metavar("percentage").help("dynamic range");
    arguments.add_argument("-e", "--exposure").scan<'g', float>().metavar("scale").help("exposure");
    arguments.add_argument("-b", "--brightness").scan<'g', float>().metavar("bias").help("brightness");
    arguments.add_argument("-c", "--contrast").scan<'g', float>().metavar("factor").help("contrast");
    arguments.add_argument("-s", "--sharpening").scan<'g', float>().metavar("factor").help("sharpening");
    arguments.add_argument("-g", "--clipped-chroma-recovery").scan<'g', float>().metavar("factor").help("clipped chroma recovery");
    auto& rotation_argument = arguments.add_argument("-r", "--rotation").metavar("orientation").help("image rotation");
    for (const auto& [name, _] : encre::rotation_by_name) {
        rotation_argument.add_choice(name);
    }

    try {
        arguments.parse_args(arg_count, arg_values);
    } catch (const std::exception& err) {
        std::cerr << err.what() << std::endl;
        std::cerr << arguments;
        return 1;
    }

    const auto width = arguments.get<uint32_t>("-w");
    const auto height = arguments.get<uint32_t>("-h");

    const std::filesystem::path input_image_path = arguments.get("input_image");

    std::filesystem::path output_image_path = arguments.get("-o");
    if (output_image_path == "-") {
        output_image_path = std::filesystem::path(input_image_path).replace_extension(".bin");
    }

    std::filesystem::path preview_image_path = arguments.is_used("-p") ? arguments.get("-p") : "";
    if (preview_image_path == "-") {
        preview_image_path = (output_image_path.parent_path() / (output_image_path.stem() += "_preview.png"));
    }

    encre::Options options{};
    if (const auto value = arguments.present("-r"))
        options.rotation = encre::rotation_by_name.at(*value);
    read_option(arguments, "-v", options.dynamic_range);
    read_option(arguments, "-e", options.exposure);
    read_option(arguments, "-b", options.brightness);
    read_option(arguments, "-c", options.contrast);
    read_option(arguments, "-s", options.sharpening);
    read_option(arguments, "-g", options.clipped_chroma_recovery);

    encre::initialize(arg_values[0]);

    std::vector<uint8_t> output;
    output.resize(width * height);
    if (encre::convert(input_image_path.c_str(), width, height, encre::waveshare_7dot3_inch_e_paper_f_palette, options,
            output, preview_image_path.empty() ? nullptr : preview_image_path.c_str())) {
        std::ofstream fs{output_image_path, std::ios::binary};
        fs.write(reinterpret_cast<const char*>(output.data()), output.size() * sizeof(uint8_t));
    } else {
        std::cerr << "Failed\n";
    }

    encre::uninitalize();
}
