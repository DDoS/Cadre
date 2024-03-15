#pragma once

#include "encre.hpp"

#include <cmath>

namespace vips {
    class VImage;
}

namespace encre {
    constexpr glm::mat3 xyz_to_lms{
        {0.8189330101f, 0.0329845436f, 0.0482003018f},
        {0.3618667424f, 0.9293118715f, 0.2643662691f},
        {-0.1288597137f, 0.0361456387f, 0.6338517070f}
    };
    const glm::mat3 lms_to_xyz = glm::inverse(xyz_to_lms);
    constexpr glm::mat3 lmsP_to_oklab{
        {0.2104542553f, 1.9779984951f, 0.0259040371f},
        {0.7936177850f, -2.4285922050f, 0.7827717662f},
        {-0.0040720468f, 0.4505937099f, -0.8086757660f}
    };
    const glm::mat3 oklab_to_lmsP = glm::inverse(lmsP_to_oklab);

    inline Oklab xyz_to_oklab(CIEXYZ xyz) {
        const auto lms = xyz_to_lms * (xyz / 100.f);
        const glm::vec3 lmsP{std::cbrt(lms.x), std::cbrt(lms.y), std::cbrt(lms.z)};
        const auto lab = lmsP_to_oklab * lmsP * 100.f;
        return Oklab{lab};
    }

    inline CIEXYZ oklab_to_xyz(Oklab lab) {
        const auto lmsP = oklab_to_lmsP * (lab / 100.f);
        const auto lms = lmsP * lmsP * lmsP;
        const auto xyz = lms_to_xyz * lms * 100.f;
        return CIEXYZ{xyz};
    }

    vips::VImage xyz_to_oklab(vips::VImage in);

    vips::VImage oklab_to_xyz(vips::VImage in);
}