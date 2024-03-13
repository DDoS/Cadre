#include "oklab.hpp"

#include <vips/vips8>

#include <glm/gtc/type_ptr.hpp>

namespace {
    struct XYZ2Oklab {
        VipsOperation parent_instance;
        VipsImage* in;
        VipsImage* out;
    };

    struct XYZ2OklabClass {
        VipsOperationClass parent_class;
    };

    G_DEFINE_TYPE(XYZ2Oklab, xyz_to_oklab, VIPS_TYPE_OPERATION);

    int xyz_to_oklab_generate(VipsRegion* out_region, void* vseq, void* a, void* b, gboolean* stop) {
        const auto rectangle = &out_region->valid;
        const auto region = reinterpret_cast<VipsRegion*>(vseq);
        if (vips_region_prepare(region, rectangle)) {
            return -1;
        }

        const auto xyz_to_oklab = reinterpret_cast<XYZ2Oklab*>(b);
        const auto band_count = xyz_to_oklab->in->Bands;
        const auto line_size = rectangle->width * band_count;
        for (int y = 0; y < rectangle->height; y++) {
            const auto p = reinterpret_cast<float*>(VIPS_REGION_ADDR(region, rectangle->left, rectangle->top + y));
            const auto q = reinterpret_cast<float*>(VIPS_REGION_ADDR(out_region, rectangle->left, rectangle->top + y));

            for (int x = 0; x + band_count - 1 < line_size; x += band_count) {
                const auto xyz = glm::make_vec3(p + x);
                const auto lab = static_cast<glm::vec3>(encre::xyz_to_oklab(encre::CIEXYZ{xyz}));
                std::memcpy(q + x, glm::value_ptr(lab), sizeof(lab));
                for (int b = 3; b < band_count; b++)
                    q[x + b] = p[x + b];
            }
        }

        return 0;
    }

    int xyz_to_oklab_build(VipsObject* object) {
        const auto class_ = VIPS_OBJECT_GET_CLASS(object);
        const auto xyz_to_oklab = reinterpret_cast<XYZ2Oklab*>(object);

        if (VIPS_OBJECT_CLASS(xyz_to_oklab_parent_class)->build(object)) {
            return -1;
        }

        if (vips_check_uncoded(class_->nickname, xyz_to_oklab->in) ||
                vips_check_bands_atleast(class_->nickname, xyz_to_oklab->in, 3) ||
                vips_check_format(class_->nickname, xyz_to_oklab->in, VIPS_FORMAT_FLOAT)) {
            return -1;
        }

        g_object_set(object, "out", vips_image_new(), NULL);

        if (vips_image_pipelinev(xyz_to_oklab->out, VIPS_DEMAND_STYLE_THINSTRIP, xyz_to_oklab->in, NULL)) {
            return -1;
        }

        xyz_to_oklab->out->Type = VIPS_INTERPRETATION_LAB;

        if (vips_image_generate(xyz_to_oklab->out, vips_start_one, xyz_to_oklab_generate, vips_stop_one,
                xyz_to_oklab->in, xyz_to_oklab)) {
            return -1;
        }

        return 0;
    }

    void xyz_to_oklab_class_init(XYZ2OklabClass* class_) {
        const auto gobject_class = G_OBJECT_CLASS(class_);
        const auto object_class = reinterpret_cast<VipsObjectClass*>(class_);

        gobject_class->set_property = vips_object_set_property;
        gobject_class->get_property = vips_object_get_property;

        object_class->nickname = "xyz_to_oklab";
        object_class->description = "transform CIE XYZ to Oklab";
        object_class->build = xyz_to_oklab_build;

        VIPS_ARG_IMAGE(class_, "in", 1, "Input", "Input image", VIPS_ARGUMENT_REQUIRED_INPUT, G_STRUCT_OFFSET(XYZ2Oklab, in));
        VIPS_ARG_IMAGE(class_, "out", 2, "Output", "Output image", VIPS_ARGUMENT_REQUIRED_OUTPUT, G_STRUCT_OFFSET(XYZ2Oklab, out));
    }

    void xyz_to_oklab_init(XYZ2Oklab*) {
    }

    struct Oklab2XYZ {
        VipsOperation parent_instance;
        VipsImage* in;
        VipsImage* out;
    };

    struct Oklab2XYZClass {
        VipsOperationClass parent_class;
    };

    G_DEFINE_TYPE(Oklab2XYZ, oklab_to_xyz, VIPS_TYPE_OPERATION);

    int oklab_to_xyz_generate(VipsRegion* out_region, void* vseq, void* a, void* b, gboolean* stop) {
        const auto rectangle = &out_region->valid;
        const auto region = reinterpret_cast<VipsRegion*>(vseq);
        if (vips_region_prepare(region, rectangle)) {
            return -1;
        }

        const auto oklab_to_xyz = reinterpret_cast<Oklab2XYZ*>(b);
        const auto band_count = oklab_to_xyz->in->Bands;
        const auto line_size = rectangle->width * band_count;
        for (int y = 0; y < rectangle->height; y++) {
            const auto p = reinterpret_cast<float*>(VIPS_REGION_ADDR(region, rectangle->left, rectangle->top + y));
            const auto q = reinterpret_cast<float*>(VIPS_REGION_ADDR(out_region, rectangle->left, rectangle->top + y));

            for (int x = 0; x + band_count - 1 < line_size; x += band_count) {
                const auto lab = encre::Oklab{p[x + 0], p[x + 1], p[x + 2]};
                const auto xyz = encre::oklab_to_xyz(lab);
                q[x + 0] = xyz.x;
                q[x + 1] = xyz.y;
                q[x + 2] = xyz.z;
                for (int b = 3; b < band_count; b++)
                    q[x + b] = p[x + b];
            }
        }

        return 0;
    }

    int oklab_to_xyz_build(VipsObject* object) {
        const auto class_ = VIPS_OBJECT_GET_CLASS(object);
        const auto oklab_to_xyz = reinterpret_cast<Oklab2XYZ*>(object);

        if (VIPS_OBJECT_CLASS(oklab_to_xyz_parent_class)->build(object)) {
            return -1;
        }

        if (vips_check_uncoded(class_->nickname, oklab_to_xyz->in) ||
                vips_check_bands_atleast(class_->nickname, oklab_to_xyz->in, 3) ||
                vips_check_format(class_->nickname, oklab_to_xyz->in, VIPS_FORMAT_FLOAT)) {
            return -1;
        }

        g_object_set(object, "out", vips_image_new(), NULL);

        if (vips_image_pipelinev(oklab_to_xyz->out, VIPS_DEMAND_STYLE_THINSTRIP, oklab_to_xyz->in, NULL)) {
            return -1;
        }

        oklab_to_xyz->out->Type = VIPS_INTERPRETATION_XYZ;

        if (vips_image_generate(oklab_to_xyz->out, vips_start_one, oklab_to_xyz_generate, vips_stop_one,
                oklab_to_xyz->in, oklab_to_xyz)) {
            return -1;
        }

        return 0;
    }

    void oklab_to_xyz_class_init(Oklab2XYZClass* class_) {
        const auto gobject_class = G_OBJECT_CLASS(class_);
        const auto object_class = reinterpret_cast<VipsObjectClass*>(class_);

        gobject_class->set_property = vips_object_set_property;
        gobject_class->get_property = vips_object_get_property;

        object_class->nickname = "oklab_to_xyz";
        object_class->description = "transform Oklab CIE XYZ";
        object_class->build = oklab_to_xyz_build;

        VIPS_ARG_IMAGE(class_, "in", 1, "Input", "Input image", VIPS_ARGUMENT_REQUIRED_INPUT, G_STRUCT_OFFSET(Oklab2XYZ, in));
        VIPS_ARG_IMAGE(class_, "out", 2, "Output", "Output image", VIPS_ARGUMENT_REQUIRED_OUTPUT, G_STRUCT_OFFSET(Oklab2XYZ, out));
    }

    void oklab_to_xyz_init(Oklab2XYZ*) {
    }
}

namespace encre {
    vips::VImage xyz_to_oklab(vips::VImage in) {
        xyz_to_oklab_get_type();

        vips::VImage out;
        in.call("xyz_to_oklab", vips::VImage::option()->set("in", in)->set("out", &out));
        return out;
    }

    vips::VImage oklab_to_xyz(vips::VImage in) {
        oklab_to_xyz_get_type();

        vips::VImage out;
        in.call("oklab_to_xyz", vips::VImage::option()->set("in", in)->set("out", &out));
        return out;
    }
}
