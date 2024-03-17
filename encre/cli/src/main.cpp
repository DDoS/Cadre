#include <encre.hpp>

#include <iostream>
#include <fstream>
#include <filesystem>

int main(int arg_count, char** arg_values) {
    if (arg_count <= 1) {
        std::cout << "Usage: <input_image> [<output_binary> | -] [<output_dithered_image> | -]\n";
    }

    if (arg_count < 2 || arg_count > 4) {
        std::cerr << "Expected 1 to 3 argument\n";
        return 1;
    }

    const std::filesystem::path input_image_path = arg_values[1];

    std::filesystem::path output_image_path = arg_count > 2 ? arg_values[2] : "";
    if (output_image_path.empty() || output_image_path == "-") {
        output_image_path = std::filesystem::path(input_image_path).replace_extension(".bin");
    }

    std::filesystem::path dithered_image_path = arg_count > 3 ? arg_values[3] : "";
    if (dithered_image_path == "-") {
        dithered_image_path = (output_image_path.parent_path() / (output_image_path.stem() += "_dithered.png"));
    }

    encre::initialize(arg_values[0]);

    static constexpr uint32_t width = 800, height = 480;

    std::vector<uint8_t> dithered;
    dithered.resize(width * height);
    if (encre::convert(input_image_path.c_str(), width, height, encre::waveshare_7dot3_inch_e_paper_f_palette,
            dithered, dithered_image_path.empty() ? nullptr : dithered_image_path.c_str())) {
        std::ofstream fs{output_image_path, std::ios::binary};
        fs.write(reinterpret_cast<const char*>(dithered.data()), dithered.size() * sizeof(uint8_t));
    } else {
        std::cerr << "Failed\n";
    }

    encre::uninitalize();
}
