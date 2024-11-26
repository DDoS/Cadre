#include "encre.hpp"

#define GLM_ENABLE_EXPERIMENTAL
#include <glm/gtc/integer.hpp>
#include <glm/gtx/norm.hpp>

#include <array>
#include <algorithm>
#include <fstream>
#include <iostream>

namespace {
    struct alignas(4) Header {
        static constexpr std::array encre_magic = std::to_array(u8"encre");

        std::remove_cv_t<decltype(encre_magic)> magic{};
        uint8_t bits_per_color;
        encre::Rotation rotation;
        uint16_t palette_size{};
        uint16_t width{}, height{};
    };

    std::optional<Header> read_encre_header(std::ifstream& stream, const char* image_path) {
        if (!image_path) {
            std::cerr << "Image path is null" << std::endl;
            return std::nullopt;
        }

        stream = std::ifstream{image_path, std::ios_base::binary};

        Header header{};
        if (!stream.read(reinterpret_cast<char*>(&header), sizeof(header))) {
            return std::nullopt;
        }

        if (header.magic != Header::encre_magic) {
            return std::nullopt;
        }

        return header;
    }

    bool read_encre_body(std::ifstream& stream, const Header& header,
            std::span<encre::Oklab> palette_points, std::span<uint8_t> output) {
        const auto read_bytes = [&stream]<typename T, size_t size>(
                std::span<T, size> buffer, size_t max_length = std::numeric_limits<size_t>::max()) {
            return static_cast<bool>(stream.read(reinterpret_cast<char*>(buffer.data()),
                    std::min(buffer.size_bytes(), max_length)));
        };

        if (!read_bytes(palette_points)) {
            std::cerr << "Couldn't read palette data" << std::endl;
            return false;
        }

        const auto color_byte_count = (output.size() * header.bits_per_color + 7) / 8;

        std::array<uint8_t, 4096> buffer{};
        const auto fill_color_buffer  = [&](size_t size = std::numeric_limits<size_t>::max()) {
            if (!read_bytes(std::span{buffer}, std::min(buffer.size(), size))) {
                std::cerr << "Couldn't read color data" << std::endl;
                return false;
            }

            return true;
        };

        if (!fill_color_buffer(color_byte_count)) {
            return false;
        }

        const auto mask = (1 << header.bits_per_color) - 1;
        uint32_t bit_index = 0;
        size_t bytes_read = 0;
        for (uint8_t& color : output) {
            const auto byte_index = bit_index >> 3;
            const auto bit_offset = bit_index & 7;
            color = (buffer[byte_index] >> bit_offset) & mask;

            auto next_byte_index = (bit_index + header.bits_per_color) >> 3;
            if (byte_index != next_byte_index) {
                if (next_byte_index >= buffer.size()) {
                    bytes_read += buffer.size();
                    if (!fill_color_buffer(color_byte_count - bytes_read)) {
                        return false;
                    }

                    next_byte_index = 0;
                }

                const auto next_bit_offset = 8 - bit_offset;
                const auto next_mask = mask >> next_bit_offset << next_bit_offset;
                color |= (buffer[next_byte_index] << next_bit_offset) & next_mask;
            }

            bit_index = (bit_index + header.bits_per_color) % (buffer.size() * 8);
        }

        return true;
    }
}

namespace encre {
    bool write_encre_file(std::span<const uint8_t> converted, uint32_t width, std::span<const Oklab> palette_points,
            const Rotation& output_rotation, const char* image_path) {
        if (!image_path) {
            std::cerr << "Image path is null" << std::endl;
            return false;
        }

        const uint32_t height = converted.size() / width;
        if (height <= 0) {
            std::cerr << "Input buffer is too small" << std::endl;
            return false;
        }

        if (width > std::numeric_limits<uint16_t>::max() ||
                height > std::numeric_limits<uint16_t>::max() ||
                palette_points.size() > std::numeric_limits<uint16_t>::max()) {
            std::cerr << "Data too big" << std::endl;
            return false;
        }

        const auto bits_per_color = static_cast<uint8_t>(glm::log2(palette_points.size()) + 1);

        Header header{};
        header.magic = Header::encre_magic;
        header.bits_per_color = bits_per_color;
        header.rotation = output_rotation;
        header.palette_size = static_cast<uint16_t>(palette_points.size());
        header.width = static_cast<uint16_t>(width);
        header.height = static_cast<uint16_t>(height);

        std::ofstream stream{image_path, std::ios_base::binary | std::ios_base::trunc};
        if (!stream) {
            std::cerr << "Couldn't open file" << std::endl;
            return false;
        }

        if (!stream.write(reinterpret_cast<const char*>(&header), sizeof(header))) {
            std::cerr << "Couldn't write header" << std::endl;
            return false;
        }

        if (!stream.write(reinterpret_cast<const char*>(palette_points.data()), palette_points.size_bytes())) {
            std::cerr << "Couldn't write palette data" << std::endl;
            return false;
        }

        std::array<uint8_t, 4096> buffer{};
        uint32_t bit_index = 0;
        const auto flush_color_buffer = [&](size_t size = std::numeric_limits<size_t>::max()) {
            if (!stream.write(reinterpret_cast<const char*>(buffer.data()), std::min(size, buffer.size()))) {
                std::cerr << "Couldn't write color data" << std::endl;
                return false;
            }

            return true;
        };

        const auto mask = (1 << bits_per_color) - 1;
        for (uint32_t color : converted) {
            color = (color & mask) << (bit_index & 7);
            const auto byte_index = bit_index >> 3;
            buffer[byte_index] |= static_cast<uint8_t>(color);

            auto next_byte_index = (bit_index + bits_per_color) >> 3;
            if (byte_index != next_byte_index) {
                if (next_byte_index >= buffer.size()) {
                    if (!flush_color_buffer()) {
                        return false;
                    }

                    buffer.fill(0);
                    next_byte_index = 0;
                }

                buffer[next_byte_index] |= static_cast<uint8_t>(color >> 8);
            }

            bit_index = (bit_index + bits_per_color) % (buffer.size() * 8);
        }

        if (bit_index > 0 && !flush_color_buffer((bit_index + 7) / 8)) {
            return false;
        }

        return true;
    }

    bool read_encre_file(const char* image_path, std::vector<uint8_t>& output, uint32_t& width,
            std::vector<Oklab>& palette_points, Rotation& output_rotation) {
        std::ifstream stream{};
        Header header{};
        if (const auto maybe_header = read_encre_header(stream, image_path)) {
            header = *maybe_header;
        } else {
            std::cerr << "Invalid header (wrong file type?)" << std::endl;
            return false;
        }

        width = header.width;
        output_rotation = header.rotation;

        palette_points.resize(header.palette_size);

        const auto color_count = static_cast<uint32_t>(header.width) * header.height;
        output.resize(color_count);

        return read_encre_body(stream, header, palette_points, output);
    }

    bool read_compatible_encre_file(const char* image_path, uint32_t width, size_t palette_size,
            std::span<uint8_t> output, Rotation* output_rotation) {
        std::ifstream stream{};
        Header header{};
        if (const auto maybe_header = read_encre_header(stream, image_path)) {
            header = *maybe_header;
        } else {
            return false;
        }

        const uint32_t height = output.size() / width;
        if (height <= 0) {
            std::cerr << "Output buffer is too small" << std::endl;
            return false;
        }

        if (width != header.width || height != header.height || palette_size != header.palette_size) {
            return false;
        }

        width = header.width;
        if (output_rotation) {
            *output_rotation = header.rotation;
        }

        std::vector<Oklab> palette;
        palette.resize(header.palette_size);
        if (!read_encre_body(stream, header, palette, output)) {
            return false;
        }

        return true;
    }
}
