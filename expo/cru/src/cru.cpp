#include "libraw/libraw.h"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/chrono.h>

#include <optional>
#include <chrono>

namespace py = pybind11;

namespace {
    struct image_info {
        int width = 0, height = 0;
        std::optional<std::chrono::time_point<std::chrono::system_clock>> capture_date;
    };

    std::optional<image_info> load_image_info(const char* path) {
        LibRaw raw_processor;
        const auto result = raw_processor.open_file(path);
        switch (result) {
            case LIBRAW_SUCCESS:
                break;
            case LIBRAW_FILE_UNSUPPORTED:
            case LIBRAW_NOT_IMPLEMENTED:
                return std::nullopt;
            default:
                throw std::runtime_error{"Error reading raw image (code " + std::to_string(result) + ")"};
        }

        // Raw image size isn't the final processed image size
        // (in fact it's a bit bigger), but aspect ratio is what matters.
        // Flip bits 1 and 2 only mirror horizontally and vertically.
        // This has no effect on the image size.

        const auto& data = raw_processor.imgdata;
        auto width = data.sizes.width;
        auto height = data.sizes.height;
        if (data.sizes.flip & 4) {
            std::swap(width, height);
        }

        std::optional<std::chrono::time_point<std::chrono::system_clock>> capture_date;
        if (data.other.timestamp > 0) {
            capture_date = std::chrono::system_clock::from_time_t(data.other.timestamp);
        }

        return image_info{.width = width, .height = height, .capture_date = capture_date};
    }
}

PYBIND11_MODULE(cru, m) {
    m.doc() = "Python bindings for Cru";

    py::class_<image_info>(m, "ImageInfo").
        def_readwrite("width", &image_info::width).
        def_readwrite("height", &image_info::height).
        def_readwrite("capture_date", &image_info::capture_date);

    m.def("load_image_info", &load_image_info, py::arg("path"), "Load raw image data");
}
