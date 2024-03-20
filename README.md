# Cadre

Cadre is a colour e-ink picture frame project. It aims for:
- Improved colour accuracy,
- Cloud photo hosting integration
- Easy deployment.

It's split up into multiple components:
- [Encre](#encre): convert image files to a native e-ink display palette
- [Affiche](#affiche): Local web interface
- [Album](#album): Cloud photo hosting integration

## Encre

*Convert images to an e-ink display palette.*

Functionally complete. Exposes both a C++ and a Python API.

This module reads images files (any format supported by your libvips install),
performs perceptual gamut mapping, and dithers to the e-ink display palette.

Samples results are available in [test_data](encre/test_data). Keep in mind that
the currently available colour e-ink displays have very low gamut, so it's
normal that the images look washed out. That's what it looks like on the
actual display. This tool focuses on at least keeping the colours as true
to the originals are possible.

### Build (draft)

- Install Vcpkg
- Install pkg-config
- Install libvips (8.15.1 or newer)
- Run `cmake --preset release && cmake --build --preset release`

Other dependencies are installed by Vcpkg.

You might have to upgrade CMake, Python or your C++ compiler, the logs should tell you.

There are additional notes specific to the "Raspberry PI Zero 2 W" [here](encre/rpi_build_notes.txt).

### Running

If the build succeeds, you can use the CLI tool at `build/release/cli/encre-cli` to
test image conversions. For example: `build/release/cli/encre-cli test_data/colors.png -p`
will output `test_data/colors.bin` (palette'd image as raw unsigned bytes) and
`test_data/colors_preview.png` as a preview. Run with `-h` for more information.

If you're running on a machine that has the "Pimoroni Inky" Python library installed, you
can use [write_to_display.py](encre/misc/write_to_display.py) instead to directly write an image
to the display. This still assumes an ACeP 7-Color e-ink display, but handles other sizes.
To use a different palette, call `py_encre.make_palette_xyz` or `py_encre.make_palette_lab`.
If you're lucky, your display data sheet will have the CIE Lab values for each colour,
otherwise you can eyeball them... An example is available [here](encre/misc/rgb_palette_example.py).

## Affiche

*Local web interface*

After building [Encre](#encre), create a Python virtual environment, and install the
[requirements](affiche/requirements.txt) using `pip`. Start the server using
`start.sh`. Use `stop.sh` if you need to stop the server if it's running in the background.
You will likely need to run using sudo to bind to port `80`.

The server should be available at the host's LAN address. This will depend on your
system settings.

[<img src="images/affiche_screenshot.jpeg" width="250"/>](images/affiche_screenshot.jpeg)

## Album

*Coming soon*
