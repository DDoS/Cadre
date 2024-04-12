# Cadre

Cadre is a colour e-ink picture frame project. It aims for:
- Improved colour accuracy
- Simple web interface
- Automatic photo updates from your collections
- Easy deployment

It's split up into multiple components:
- [Encre](#encre): convert image files to a native e-ink display palette
- [Affiche](#affiche): Local web interface
- [Expo](#expo): Automatic photo updates

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
- Run `cmake --workflow --preset release`

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
`start.sh`. Use `stop.sh` if you need to stop the server when it's running in the background.
You might need to change system settings to make port `80` available without privileges.
The simplest solution is to run `sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80`.

The server should be available at the host's LAN address on port `80`.

[<img src="images/affiche_screenshot.jpeg" width="250"/>](images/affiche_screenshot.jpeg)

##  Expo

*Automatic photo update service*

This is an optional component. It's a separate service which maintains a database of photos locations and metadata,
and periodically posts one to Affiche.

Create a Python virtual environment, and install the [requirements](expo/requirements.txt) using `pip`.
Start the server using `start.sh`. Use `stop.sh` if you need to stop the server when it's running in the background.

The server should be available at the host's LAN address on port `21110`.
You can run Expo on the same host as Affiche or a different one.

So far Expo only supports local filesystem collections. You can run the service on your photo NAS,
or on a Raspberry Pi with an SMB share where you can copy your favorite photos.
If you need raw photo format support, checkout [Cru](expo/cru).

### Collections

List all collections by `GET`ing from `/collections`.
Create a collection by `PUT`ting to `/collections` a JSON object like so:
```json
{
    "identifier": "my_collection",
    "display_name": "My Collection",
    "schedule": "*/5 * * * *",
    "class_name": "FileSystemCollection",
    "settings": {
        "root_path": "<path to your local photos folder>"
    }
}
```
- `identifier` must be unique
- `display_name` is optional and defaults to the `identifier` value
- `schedule` uses the Cron format
- `class_name` can only be `FileSystemCollection`
- `settings` depends on the `class_name` value

You can edit a collection by `PATCH`ing to `/collections?identifier=<identifier>` using the same JSON format,
except all fields are now optional. You can also query using `GET`, and delete using `DELETE`.

#### FileSystemCollection

Scan the `root_path` for known image formats. Uses `libvips` through the `pyvips` wrapper to load image headers.
Optionally uses [Cru](expo/cru) if it's been built.

Does not support the `favorite` filter.

### Schedules

The schedule API uses the same methods as collections, but on the `/schedules` endpoint.
The JSON format is:
```json
{
    "identifier": "my_schedule",
    "display_name": "My Schedule",
    "hostname": "<Affiche hostname>",
    "schedule": "*/20 * * * *",
    "enabled": true,
    "filter": "<filter expression>"
}
```
- `identifier` must be unique
- `display_name` is optional and defaults to the `identifier` value
- `schedule` uses the Cron format
- `hostname` is the hostname (optionally with a `:<port>` suffix) where an Affiche instance is running
- `enabled` is optional and defaults to `true`
- `filter` is optional and defaults to `"true"`

#### Filter expressions

The filter EBNF grammar is:
```ebnf
bool literal = "false" | "true";
favorite = "favorite";
aspect = "landscape" | "portrait" | "square";
parenthesized expression = "(", expression, ")";
atom = bool literal | favorite | aspect | parenthesized expression;

unary = ["not"], atom;
and = unary, ["and", unary];
or = and, ["or", and];

expression = or;
```

In simple terms this means you can use the `favorite` (unused), `landscape`, `portrait` and `square`
predicates to write a logical expression for filtering photos. You can use the `()`, `not`, `and`, and `or`
operators to build your expression (listed in decreasing order of precedence). The `true` and `false`
literals are also available: if you simply want to allow all photos use `true`.

### Refresh

Immediately trigger a schedule by `POST`ing to `/refresh` a JSON object like so:
```json
{
    "identifier": "<schedule identifier>",
    "delay": 0
}
```
- `identifier` is a schedule identifier
- `delay` a delay in seconds (float), is optional and defaults to `0`
