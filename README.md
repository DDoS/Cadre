# Cadre

Cadre is a colour e-ink picture frame project. It aims for improved colour accuracy,
and cloud photo hosting integration, and easy deployment.

It's split up into multiple components:
- Encre: convert image files to a native e-ink display palette
- Affiche: Local web interface
- Album: Cloud photo hosting integration

## Encre

*Convert image files to a native e-ink display palette.*

Functionally complete. Exposes both a C++ and a Python API.

This module reads images files (any format supported by your libvips install),
performs perceptual gamut mapping, and dithers to the e-ink display palette.

Samples results are available in [test_data](test_data). Keep in mind that
the currently available colour e-ink displays have very low gamut, so it's
normal that the images look washed out. That's what it looks like on the
actual display. This tool focuses on at least keeping the colours as true
to the originals are possible.

### Build (draft)

- Install Vcpkg
- Install pkg-config
- Install libvips
- Run `cmake --preset release && cmake --build --preset release`

Other dependencies are installed by Vcpkg.

You might have to upgrade CMake, Python or your C++ compiler, the logs should tell you.

There are additional notes specific to the "Raspberry PI Zero 2 W" [here](rp_build_notes.txt).

### Running (draft)

If the build succeeds, you can use the CLI tool at `build/release/cli/encre-cli` to
test image conversions. For example: `build/release/cli/encre-cli test_data/colors.png - -`
will output `test_data/colors.bin` (palette'd image as raw unsigned bytes) and
`test_data/colors_dithered.png` as a preview. Currently the CLI assumes the target display
is a "7.3inch ACeP 7-Color E-Ink Display, 800×480 Pixels".

If you're running on a machine that has the "Pimoroni Inky" Python library installed, you
can use [write_to_display.py](misc/write_to_display.py) instead to directly write an image
to the display. This still assumes an ACeP 7-Color e-ink display, but handles other sizes.
To use a different palette, call `py_encre.make_palette_xyz` or `py_encre.make_palette_lab`.
If you're lucky, your display data sheet will have the CIE Lab values for each colour,
otherwise you can eyeball them... An example is available [here](misc/srgb_palette_example.py).

## Affiche

*Coming soon*

## Album

*Coming soon*