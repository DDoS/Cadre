#include <encre.hpp>

#include <argparse/argparse.hpp>

#include <iostream>
#include <fstream>
#include <filesystem>

int main(int arg_count, char** arg_values) {
    argparse::ArgumentParser arguments("encre-cli", "0.0.1");
    arguments.add_description("Command line interface for Encre");
    arguments.add_argument("input_image");
    arguments.add_argument("-w", "--width").scan<'u', uint32_t>().metavar("width").help("output width").default_value(800u);
    arguments.add_argument("-h", "--height").scan<'u', uint32_t>().metavar("height").help("output height").default_value(480u);
    arguments.add_argument("-o", "--out").metavar("output_binary").help("output binary").default_value("-");
    arguments.add_argument("-p", "--preview").metavar("output_preview_image").help("output preview image").default_value("-");
    arguments.add_argument("-v", "--contrast-coverage-percent").scan<'g', float>().metavar("percentage").help("contrast coverage percent");
    arguments.add_argument("-c", "--contrast-compression").scan<'g', float>().metavar("factor").help("contrast compression");
    arguments.add_argument("-g", "--clipped-gamut-recovery").scan<'g', float>().metavar("factor").help("clipped gamut recovery");
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
    if (const auto value = arguments.present<float>("-v"))
        options.contrast_coverage = *value;
    if (const auto value = arguments.present<float>("-c"))
        options.contrast_compression = *value;
    if (const auto value = arguments.present<float>("-g"))
        options.clipped_gamut_recovery = *value;

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
