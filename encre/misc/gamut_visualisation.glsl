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

const int palette_hull_facet_count = 10;
const vec4[palette_hull_facet_count] palette_hull = vec4[palette_hull_facet_count](
    vec4(0.3244, 0.87509, 0.359142, -29.7101),
    vec4(0.188987, -0.977347, -0.0952675, -17.192),
    vec4(-0.137374, 0.806091, -0.575626, 1.82368),
    vec4(0.136985, 0.669424, -0.730142, -11.9776),
    vec4(-0.281489, -0.872841, -0.398639, 10.9129),
    vec4(0.100215, -0.753107, -0.650221, -8.75222),
    vec4(0.322903, 0.873958, 0.363223, -29.6286),
    vec4(-0.223619, -0.113394, 0.968058, 8.43461),
    vec4(-0.32781, 0.120444, 0.937035, 13.7296),
    vec4(-0.301063, -0.0618804, 0.951594, 13.1911)
);
const vec2 gray_line = vec2(43.8149, 87.3344) / 100.0;
const float lightness_adaptation_factor = 5.0;

bool lab_inside_palette_gamut(vec3 lab) {
    for (int i = 0; i < palette_hull_facet_count; i++) {
        if (dot(vec4(lab, 0.01), palette_hull[i]) > 1e-4)
            return false;
    }

    return true;
}

// From https://bottosson.github.io/posts/gamutclipping/#adaptive-%2C-hue-independent
vec3 compute_gamut_clamp_target(float alpha, const float l, const float chroma) {
    float range = gray_line.y - gray_line.x;

    float l_start = (l - gray_line.x) / range;
    float l_diff = l_start - 0.5;
    float e_1 = 0.5 + abs(l_diff) + alpha * chroma;
    float l_target = (1.0 + sign(l_diff) * (e_1 - sqrt(max(0.0, e_1 * e_1 - 2.0 * abs(l_diff))))) * 0.5;

    return vec3(l_target * range + gray_line.x, 0, 0);
}

vec3 clamp_to_palette_gamut(vec3 lab) {
    float chroma = length(lab.yz);
    float alpha = lightness_adaptation_factor;
    vec2 min_max_gray = gray_line + vec2(1e-4, -1e-4);
    if (chroma < 1e-4 || alpha < 1e-4 && (lab.x < min_max_gray.x || lab.x > min_max_gray.y)) {
        return vec3(clamp(lab.x, gray_line.x, gray_line.y), 0, 0);
    }

    vec3 target = compute_gamut_clamp_target(alpha, lab.x, chroma);
    vec3 clamp_direction = normalize(target - lab);
    vec2 hue_chroma = normalize(lab.yz);

    vec3 clamped_lab = vec3(1);
    float closest_distance_to_target = 1e10;
    for (int i = 0; i < palette_hull_facet_count; i++) {
        vec4 plane = palette_hull[i];

        float d = dot(clamp_direction, plane.xyz);
        if (d > -1e-4) {
            continue;
        }

        float t = -dot(vec4(lab, 0.01), plane) / d;
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

    vec2 lc = uv.yx * vec2(1, 0.12);
    float h = radians(mod(iTime * 30.0, 360.0));
    vec3 lch = vec3(lc, h);
    vec3 lab = oklab_from_oklch(lch);

    float f = 1.0;
    if (!lab_inside_palette_gamut(lab)) {
        lab = clamp_to_palette_gamut(lab);
        f = 0.75;
    }

    if (!lab_inside_palette_gamut(lab)) {
        lab = vec3(1, 1, 0); // Problem!
    }

    vec3 srgb = linear_srgb_from_oklab(lab) * f;
    frag_color = vec4(srgb_from_linear_srgb(srgb), 1);
}