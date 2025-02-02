// Shadertoy script to show how the Oklab gamut is mapped to the palette
// Paste and run at https://www.shadertoy.com/new

vec3 srgb_from_linear_srgb(vec3 x) {
    vec3 xlo = 12.92 * x;
    vec3 xhi = 1.055 * pow(x, vec3(0.4166666666666667)) - 0.055;
    return mix(xlo, xhi, step(vec3(0.0031308), x));
}

vec3 linear_srgb_from_srgb(vec3 x) {
    vec3 xlo = x / 12.92;
    vec3 xhi = pow((x + 0.055)/(1.055), vec3(2.4));
    return mix(xlo, xhi, step(vec3(0.04045), x));
}

const mat3 fwdA = mat3(
    1.0, 1.0, 1.0,
    0.3963377774, -0.1055613458, -0.0894841775,
    0.2158037573, -0.0638541728, -1.2914855480);

const mat3 fwdB = mat3(
    4.0767245293, -1.2681437731, -0.0041119885,
    -3.3072168827, 2.6093323231, -0.7034763098,
    0.2307590544, -0.3411344290,  1.7068625689);

const mat3 invB = mat3(
    0.4121656120, 0.2118591070, 0.0883097947,
    0.5362752080, 0.6807189584, 0.2818474174,
    0.0514575653, 0.1074065790, 0.6302613616);

const mat3 invA = mat3(
    0.2104542553, 1.9779984951, 0.0259040371,
    0.7936177850, -2.4285922050, 0.7827717662,
   -0.0040720468, 0.4505937099, -0.8086757660);

vec3 oklab_from_linear_srgb(vec3 c) {
    vec3 lms = invB * c;
    return invA * (sign(lms)*pow(abs(lms), vec3(0.3333333333333)));
}

vec3 linear_srgb_from_oklab(vec3 c) {
    vec3 lms = fwdA * c;
    return fwdB * (lms * lms * lms);
}

vec3 oklch_from_oklab(vec3 c) {
    return vec3(c.x, length(c.yz), atan(c.z, c.y));
}

vec3 oklab_from_oklch(vec3 c) {
    return vec3(c.x, c.y * cos(c.z), c.y * sin(c.z));
}

bool inside_srgb_gamut(vec3 c) {
    return all(greaterThan(c, vec3(0.0))) && all(lessThan(c, vec3(1.0)));
}

const int palette_vertex_count = 6;
const vec3[palette_vertex_count] palette_vertices = vec3[palette_vertex_count](
    vec3(49.9074, -6.67006, 5.35445) / 100.0,
    vec3(75.5561, -1.7477, 16.2378) / 100.0,
    vec3(80, -0.23354, 0.533135) / 100.0,
    vec3(46.5118, -2.62564, -15.3395) / 100.0,
    vec3(28.4822, 1.08724, -2.17702) / 100.0,
    vec3(42.0149, 12.5315, 6.71763) / 100.0
);
const int palette_edge_count = 12;
const mat2x3[palette_edge_count] palette_edges = mat2x3[palette_edge_count](
    mat2x3(vec3(42.0149, 12.5315, 6.71763), vec3(80, -0.23354, 0.533135)) / 100.0,
    mat2x3(vec3(75.5561, -1.7477, 16.2378), vec3(80, -0.23354, 0.533135)) / 100.0,
    mat2x3(vec3(75.5561, -1.7477, 16.2378), vec3(42.0149, 12.5315, 6.71763)) / 100.0,
    mat2x3(vec3(42.0149, 12.5315, 6.71763), vec3(28.4822, 1.08724, -2.17702)) / 100.0,
    mat2x3(vec3(46.5118, -2.62564, -15.3395), vec3(28.4822, 1.08724, -2.17702)) / 100.0,
    mat2x3(vec3(46.5118, -2.62564, -15.3395), vec3(42.0149, 12.5315, 6.71763)) / 100.0,
    mat2x3(vec3(46.5118, -2.62564, -15.3395), vec3(80, -0.23354, 0.533135)) / 100.0,
    mat2x3(vec3(49.9074, -6.67006, 5.35445), vec3(80, -0.23354, 0.533135)) / 100.0,
    mat2x3(vec3(49.9074, -6.67006, 5.35445), vec3(75.5561, -1.7477, 16.2378)) / 100.0,
    mat2x3(vec3(49.9074, -6.67006, 5.35445), vec3(46.5118, -2.62564, -15.3395)) / 100.0,
    mat2x3(vec3(49.9074, -6.67006, 5.35445), vec3(28.4822, 1.08724, -2.17702)) / 100.0,
    mat2x3(vec3(49.9074, -6.67006, 5.35445), vec3(42.0149, 12.5315, 6.71763)) / 100.0
);
const int palette_facet_count = 8;
const vec4[palette_facet_count] palette_facets = vec4[palette_facet_count](
    vec4(0.339991, 0.922032, 0.185104, -27.0826 / 100.0),
    vec4(-0.266854, 0.768024, -0.582175, 5.49817 / 100.0),
    vec4(0.191684, 0.826688, -0.529003, -14.8596 / 100.0),
    vec4(0.203379, -0.978409, -0.0367826, -16.4792 / 100.0),
    vec4(0.171019, -0.961313, -0.21594, -13.7909 / 100.0),
    vec4(-0.294465, -0.945858, -0.136542, 9.11815 / 100.0),
    vec4(-0.394742, -0.225484, 0.890694, 13.4273 / 100.0),
    vec4(-0.347991, -0.207933, 0.914148, 11.0856 / 100.0)
);
const vec2 gray_range = vec2(34.0155, 77.5215) / 100.0;

const float lightness_adaptation_factor = 1.0;
const float gray_chroma_tolerance = 0.025;

bool lab_inside_palette_gamut(vec3 lab) {
    for (int i = 0; i < palette_facet_count; i++) {
        if (dot(vec4(lab, 1.0), palette_facets[i]) > 1e-4)
            return false;
    }

    return true;
}

mat3 find_hue_extrema(vec3 lab) {
    vec3 hue_normal = normalize(vec3(0, -lab.z, lab.y));

    mat3x2 lc_at_extrema = mat3x2(vec2(0, 0), vec2(1e10, 0), vec2(0, 0));
    mat3 lab_at_extrema = mat3(vec3(mix(gray_range.x, gray_range.y, 0.5), 0, 0), vec3(0), vec3(0));

    for (int i = 0; i < palette_edge_count; i++) {
        vec3 edge_start = palette_edges[i][0];
        vec3 edge_delta = palette_edges[i][1] - edge_start;
        float edge_length = length(edge_delta);
        vec3 edge_direction = edge_delta / edge_length;
        float d = dot(edge_direction, hue_normal);
        if (abs(d) < 1e-4) {
            continue;
        }

        float t = dot(-edge_start, hue_normal) / d;
        if (t < 0.0 || t > edge_length) {
            continue;
        }

        vec3 intersection = edge_start + t * edge_direction;
        if (dot(lab.yz, intersection.yz) < 1e-8) {
            continue;
        }

        float intersection_chroma = length(intersection.yz);
        if (intersection_chroma > lc_at_extrema[0].y) {
            lc_at_extrema[0] = vec2(intersection.x, intersection_chroma);
            lab_at_extrema[0] = intersection;
        }
        if (intersection.x < lc_at_extrema[1].x) {
            lc_at_extrema[1] = vec2(intersection.x, intersection_chroma);
            lab_at_extrema[1] = intersection;
        }
        if (intersection.x > lc_at_extrema[2].x) {
            lc_at_extrema[2] = vec2(intersection.x, intersection_chroma);
            lab_at_extrema[2] = intersection;
        }
    }

    if (gray_range.x < lc_at_extrema[1].x) {
        lab_at_extrema[1] = vec3(gray_range.x, 0, 0);
    } else if (lc_at_extrema[1].y > gray_chroma_tolerance) {
        lab_at_extrema[1] = mix(vec3(gray_range.x, 0, 0), lab_at_extrema[1], gray_chroma_tolerance / lc_at_extrema[1].y);
    }

    if (gray_range.y > lc_at_extrema[2].x) {
        lab_at_extrema[2] = vec3(gray_range.y, 0, 0);
    } else if (lc_at_extrema[2].y > gray_chroma_tolerance) {
        lab_at_extrema[2] = mix(vec3(gray_range.y, 0, 0), lab_at_extrema[2], gray_chroma_tolerance / lc_at_extrema[2].y);
    }

    return lab_at_extrema;
}

// From https://bottosson.github.io/posts/gamutclipping/#adaptive-%2C-hue-independent
vec3 compute_gamut_clamp_target(float alpha, vec3 lab, float chroma, mat3 extrema) {
    float range = extrema[2].x - extrema[1].x;
    float l_start = (lab.x - extrema[1].x) / range;
    if (alpha < 1e-4) {
        return mix(extrema[1], extrema[2], clamp(l_start, 0.0, 1.0));
    }

    float l_diff = l_start - 0.5;
    float e_1 = 0.5 + abs(l_diff) + alpha * chroma;
    float l_target = (1.0 + sign(l_diff) * (e_1 - sqrt(max(0.0, e_1 * e_1 - 2.0 * abs(l_diff))))) * 0.5;

    return mix(extrema[1], extrema[2], l_target);
}

// From https://bottosson.github.io/posts/gamutclipping/#adaptive-%2C-hue-dependent
vec3 compute_gamut_clamp_target_hue_dependent(float alpha, vec3 lab, float chroma, mat3 extrema) {
    float range = extrema[2].x - extrema[1].x;
    float l_start = (lab.x - extrema[1].x) / range;
    if (alpha < 1e-4) {
        return mix(extrema[1], extrema[2], clamp(l_start, 0.0, 1.0));
    }

    float l_peak = (extrema[0].x - extrema[1].x) / range;
    float l_diff = l_start - l_peak;
    float k = 2.0 * (l_diff >= 0.0 ? (1.0 - l_peak) : l_peak);
    float e_1 = k / 2.0 + abs(l_diff) + alpha * chroma / k;
    float l_target = l_peak + (sign(l_diff) * (e_1 - sqrt(max(0.0, e_1 * e_1 - 2.0 * k * abs(l_diff))))) * 0.5;

    return mix(extrema[1], extrema[2], l_target);
}

vec3 clamp_to_palette_gamut(vec3 lab) {
    float chroma = length(lab.yz);
    if (chroma < 1e-4) {
        return vec3(clamp(lab.x, gray_range.x, gray_range.y), 0, 0);
    }

    float alpha = lightness_adaptation_factor;
    mat3 extrema = find_hue_extrema(lab);
    //vec3 target = compute_gamut_clamp_target(alpha, lab, chroma, extrema);
    vec3 target = compute_gamut_clamp_target_hue_dependent(alpha, lab, chroma, extrema);

    vec3 clamp_direction = normalize(target - lab);
    vec2 hue_chroma = normalize(lab.yz);

    vec3 clamped_lab = vec3(1);
    float closest_distance_to_target = 1e10;
    for (int i = 0; i < palette_facet_count; i++) {
        vec4 plane = palette_facets[i];

        float d = dot(clamp_direction, plane.xyz);
        if (d > -1e-4) {
            continue;
        }

        float t = -dot(vec4(lab, 1.0), plane) / d;
        vec3 lab_projected = lab + t * clamp_direction;

        if (dot(hue_chroma, lab_projected.yz) < -1e-4) {
            continue;
        }

        float distance_to_target = distance(target, lab_projected);
        if (distance_to_target >= closest_distance_to_target) {
            continue;
        }

        clamped_lab = lab_projected;
        closest_distance_to_target = distance_to_target;
    }

    return clamped_lab;
}

void mainImage(out vec4 frag_color, in vec2 frag_coord) {
    vec2 uv = frag_coord / iResolution.xy;

    vec2 lc = uv.yx * vec2(1, 0.165 * 2.0);
    float h = radians(mod(iTime * 30.0, 360.0));
    vec3 lch = vec3(lc, h);
    vec3 lab = oklab_from_oklch(lch);

    float f = 1.0;
    if (uv.x > 0.5) {
        mat3 extrema = find_hue_extrema(lab);
        if (uv.y < 0.333) {
            lab = extrema[1];
        } else if (uv.y < 0.667) {
            lab = extrema[0];
        } else {
            lab = extrema[2];
        }
    } else if (!lab_inside_palette_gamut(lab)) {
        lab = clamp_to_palette_gamut(lab);
        f = 0.75;
    }

    if (!lab_inside_palette_gamut(lab)) {
        ivec2 grid_coords = ivec2(frag_coord.xy / 20.0) % 2;
        if ((grid_coords.x ^ grid_coords.y) == 0) {
            lab = vec3(1, 1, 0); // Problem!
        }
    }

    vec3 srgb = linear_srgb_from_oklab(lab) * f;
    frag_color = vec4(srgb_from_linear_srgb(srgb), 1);
}
