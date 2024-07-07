#include "exif.hpp"

#include <libraw/libraw.h>

#include <vector>
#include <sstream>
#include <string_view>
#include <iterator>
#include <bit>

namespace {
    template<std::integral T>
    T byteswap(const T& value) {
        return std::byteswap(value);
    }

    template<std::integral T>
    Rational<T> byteswap(const Rational<T>& value) {
        return {std::byteswap(value.numerator), std::byteswap(value.denominator)};
    }

    template<class T>
    concept Trivial = std::is_trivial_v<T>;

    template<Trivial T>
    T to_native_endianness(T value, bool little_endian) {
        if constexpr (sizeof(T) > 1) {
            if constexpr (std::endian::native == std::endian::big) {
                if (little_endian) {
                    return byteswap(value);
                }
            } else if constexpr (std::endian::native == std::endian::little) {
                if (!little_endian) {
                    return byteswap(value);
                }
            }
        }

        return value;
    }

    template<Trivial T>
    T decode_exif_value(LibRaw_abstract_datastream& stream, bool little_endian) {
        T value{};
        stream.read(&value, sizeof(value), 1);
        return to_native_endianness(value, little_endian);
    }

    template<Trivial T>
    void clamp_exif_count(LibRaw_abstract_datastream& stream, int& count) {
        if (const auto base = stream.tell(); base + count * sizeof(T) > stream.size()) {
            count = (stream.size() - base) / sizeof(T);
        }
    }

    template<Trivial T>
    std::vector<T> decode_exif_list(LibRaw_abstract_datastream& stream, int count, bool little_endian) {
        clamp_exif_count<T>(stream, count);

       std::vector<T> value;
       value.reserve(count);
       for (int i = 0; i < count; i++) {
            value.push_back(decode_exif_value<T>(stream, little_endian));
       }

       return value;
    }

    std::string decode_exif_string(LibRaw_abstract_datastream& stream, int count, bool little_endian) {
        clamp_exif_count<char>(stream, count);

        std::string value;
        value.resize(count);
        stream.read(value.data(), sizeof(char), count);

        if (const auto null_position = value.find('\0'); null_position != std::string::npos) {
            value.resize(null_position);
        }

        return value;
    }

    template<typename U, typename T>
    std::string vector_to_string(const std::vector<T>& vector) {
        std::ostringstream stream;
        if (!vector.empty()) {
            std::copy(vector.begin(), vector.end() - 1, std::ostream_iterator<U>(stream, ", "));
            stream << static_cast<U>(vector.back());
        }

        return stream.str();
    }
}

void ExifData::parser_callback(void *context, int tag, int type, int count,
        unsigned int order, void* file, INT64 base) {
    const auto self = static_cast<ExifData*>(context);
    const auto stream = static_cast<LibRaw_abstract_datastream*>(file);
    const auto little_endian = order == 0x4949;
    switch (type) {
        case 1: {
            auto data = decode_exif_list<uint8_t>(*stream, count, little_endian);
            switch (tag) {
                case 0x50005:
                    self->gps_altitude_ref = data.at(0);
                    break;
                default:
                    break;
            }
        }
        case 2: {
            auto data = decode_exif_string(*stream, count, little_endian);
            switch (tag) {
                case 0x10010f:
                    self->make = std::move(data);
                    break;
                case 0x100110:
                    self->model = std::move(data);
                    break;
                case 0xa433:
                    self->lens_make = std::move(data);
                    break;
                case 0xa434:
                    self->lens_model = std::move(data);
                    break;
                case 0x9003:
                    self->date_time_original = std::move(data);
                    break;
                case 0x9011:
                    self->offset_time_original = std::move(data);
                    break;
                case 0x9291:
                    self->sub_sec_time_original = std::move(data);
                    break;
                case 0x50001:
                    self->gps_latitude_ref = std::move(data);
                    break;
                case 0x50003:
                    self->gps_longitude_ref = std::move(data);
                    break;
                case 0x5000c:
                    self->gps_speed_ref = std::move(data);
                    break;
                case 0x50010:
                    self->gps_img_direction_ref = std::move(data);
                    break;
                case 0x5001d:
                    self->gps_date_stamp = std::move(data);
                    break;
                default:
                    break;
            }
            break;
        }
        case 3: {
            auto data = decode_exif_list<uint16_t>(*stream, count, little_endian);
            switch (tag)
            {
                case 0xa210:
                    self->focal_plane_resolution_unit = data.at(0);
                    break;
                case 0x8827:
                    self->iso_speed_ratings = std::move(data);
                    break;
                case 0xa405:
                    self->focal_length_35mm = data.at(0);
                    break;
                default:
                    break;
            }
            break;
        }
        case 4: {
            auto data = decode_exif_list<uint32_t>(*stream, count, little_endian);
            switch (tag)
            {
                case 0x8833:
                    self->iso_speed = data.at(0);
                    break;
                default:
                    break;
            }
            break;
        }
        case 5: {
            auto data = decode_exif_list<Rational<uint32_t>>(*stream, count, little_endian);
            switch (tag)
            {
                case 0xa20e:
                    self->focal_plane_x_resolution = data.at(0);
                    break;
                case 0xa20f:
                    self->focal_plane_y_resolution = data.at(0);
                    break;
                case 0x829d:
                    self->f_number = data.at(0);
                    break;
                case 0x829a:
                    self->exposure_time = data.at(0);
                    break;
                case 0x920a:
                    self->focal_length = data.at(0);
                    break;
                case 0x50002:
                    self->gps_latitude = {data.at(0), data.at(1), data.at(2)};
                    break;
                case 0x50004:
                    self->gps_longitude = {data.at(0), data.at(1), data.at(2)};
                    break;
                case 0x50006:
                    self->gps_altitude = data.at(0);
                    break;
                case 0x5000d:
                    self->gps_speed = data.at(0);
                    break;
                case 0x50011:
                    self->gps_img_direction = data.at(0);
                    break;
                case 0x50007:
                    self->gps_time_stamp = {data.at(0), data.at(1), data.at(2)};
                    break;
                default:
                    break;
            }
            break;
        }
        case 10: {
            auto data = decode_exif_list<Rational<int32_t>>(*stream, count, little_endian);
            switch (tag) {
                case 0x9204:
                    self->exposure_compensation = data.at(0);
                    break;
                default:
                    break;
            }
            break;
        }
    }
}
