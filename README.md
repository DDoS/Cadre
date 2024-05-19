# Cadre

Cadre is a DIY picture frame project. It aims for:
- Colour e-ink display support
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
performs lightness adjustments and perceptual gamut mapping, and dithers to the e-ink display palette.

Samples results are available in [test_data](encre/test_data). Keep in mind that
the currently available colour e-ink displays have very low gamut, so it's
normal that the images look washed out. That's what it looks like on the
actual display. This tool focuses on at least keeping the colours as true
to the originals are possible.

### Build

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
to the display. This assumes an ACeP 7-Color e-ink display, but handles various resolutions.
To use a different palette, call `py_encre.make_palette_xyz` or `py_encre.make_palette_lab`.
If you're lucky, your display data sheet will have the CIE Lab values for each colour,
otherwise you can eyeball them... An example is available [here](encre/misc/rgb_palette_example.py).

## Affiche

*Local web interface*

After building [Encre](#encre), create a Python virtual environment, and install the
[requirements](affiche/requirements.txt) using `pip`. If you plan on using it with a
"Pimoroni Inky" display, then also install [requirements-inky](affiche/requirements-inky.txt)

Start the server using `start.sh`. Use `stop.sh` if you need to stop the server when it's running
in the background. You might need to change system settings to make port `80` available without
privileges. The simplest solution is to run `sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80`.

The server should be available at the host's LAN address on port `80`.

### Configuration

Copy the [default config](affiche/default_config.json) and name it `config.json`.
In this file you can overwrite the following fields:
- `TEMP_PATH`: where to write the temporary files, absolute or relative to the server executable
- `DISPLAY_WRITER_COMMAND`: the command line to run for writing a new image to the display as a list of arguments.
Must accept the `--options <json>` and `--preview <path>` arguments to pass in the display options and the preview image output path.
- `EXPO_ADDRESS`: Hostname and optional port suffix for the Expo server. Must be externally reachable (i.e.: `affiche.local` instead
of `localhost`). Optional, can be `null` to disable Expo integration. If empty, then default to the local machine network name.

[<img src="images/affiche_screenshot.png" width="400"/>](images/affiche_screenshot.jpeg)

##  Expo

*Automatic photo update service*

This is an optional component. It's a separate service which maintains a database of photos locations and metadata,
and periodically posts one to Affiche.

Create a Python virtual environment, and install the [requirements](expo/requirements.txt) using `pip`.
Additional requirements are also needed for the follow features:
- `FileSystemCollection`: [requirements-fs](expo/requirements-fs.txt)
- `AmazonPhotosCollection`: [requirements-azp](expo/requirements-azp.txt)

Start the server using `start.sh`. Use `stop.sh` if you need to stop the server when it's running in the background.

The server should be available at the host's LAN address on port `21110`.
You can run Expo on the same host as Affiche or a different one.

[<img src="images/expo_screenshot.png" width="400"/>](images/affiche_screenshot.jpeg)

### Configuration

Copy the [default config](affiche/default_config.json) and name it `config.json`.
In this file you can overwrite the following fields:
- `DB_PATH`: where to write the Expo persistent data, absolute or relative to the server executable

### Collections

You can use this by running Expo on your photo NAS, or on a Raspberry Pi with an SMB share where
you can copy your favorite photos. If you need raw photo format support, checkout [Cru](expo/cru).

List all collections by `GET`ing from `/collections`.
Create a collection by `PUT`ting to `/collections` a JSON object like so:
```json
{
    "identifier": "my_collection",
    "display_name": "My Collection",
    "schedule": "*/5 * * * *",
    "enabled": true,
    "class_name": "FileSystemCollection",
    "settings": {
        // ...
    }
}
```
- `identifier` must be unique, contain only characters in the set `[A-Za-z0-9_]`, and cannot start with a number
- `display_name` is optional and defaults to the `identifier` value
- `schedule` Cron expression, or empty string to never run automatically
- `enabled` is optional and defaults to `true`
- `class_name` can only be `FileSystemCollection`
- `settings` depends on the `class_name` value, see below

You can edit a collection by `PATCH`ing to `/collections?identifier=<identifier>` using the same JSON format,
except all fields are now optional. You can also query using `GET`, and delete using `DELETE`.

#### FileSystemCollection

Scan the `root_path` for known image formats. Uses `libvips` through the `pyvips` wrapper to load image headers.
Optionally uses [Cru](expo/cru) if it's been built.

Does not support the `favorite` filter.

Settings:
```json
{
    "root_path": "<path to your local photos folder>"
}
```

#### AmazonPhotosCollection

Uses an unofficial [Amazon Photos Python API](https://github.com/trevorhobenshield/amazon_photos) by
[Trevor Hobenshield](https://github.com/trevorhobenshield) (actually [a fork](https://github.com/DDoS/amazon_photos)
with a few improvements).

Settings:
```json
{
    "user_agent": "<User agent string from the browser used to login to Amazon Photos>",
    "cookies": {
        // See https://github.com/trevorhobenshield/amazon_photos?tab=readme-ov-file#setup
    }
}
```

### Scan

Immediately trigger a collection scan by `POST`ing to `/scan` a JSON object like so:
```json
{
    "identifier": "<collection identifier>",
    "delay": 0
}
```
- `identifier` is a collection identifier
- `delay` a delay in seconds (float), is optional and defaults to `0`

### Schedules

The schedule API uses the same methods as collections, but on the `/schedules` endpoint.
There is a new optional `hostname` argument for `GET` queries, to filter schedules by the
target hostname. It will be compared against the original hostname and the external one
if they're different (ex.: `localhost` and `affiche.local`).

The JSON format is:
```json
{
    "identifier": "my_schedule",
    "display_name": "My Schedule",
    "hostname": "<Affiche hostname>",
    "schedule": "*/20 * * * *",
    "enabled": true,
    "filter": "<filter expression>",
    "order": "<order enum name>",
    "affiche_options": {
        // ...
    }
}
```
- `identifier` must be unique, contain only characters in the set `[A-Za-z0-9_]`, and cannot start with a number
- `display_name` is optional and defaults to the `identifier` value
- `hostname` is the hostname (optionally with a `:<port>` suffix) where an Affiche instance is running
- `schedule` Cron expression, or empty string to never run automatically
- `enabled` is optional and defaults to `true`
- `filter` is optional and defaults to `"true"`
- `order` is optional and defaults to `SHUFFLE`, see below
- `affiche_options` coming soon!

#### Filter expressions

The filter EBNF grammar is:
```ebnf
bool literal = "false" | "true";
identifier = ? /[A-Za-z_][A-Za-z0-9_]*/ ?;
favorite = "favorite";
aspect = "landscape" | "portrait" | "square";
collection set = "{", identifier, {identifier}, "}";
parenthesized expression = "(", expression, ")";
atom = bool literal | favorite | aspect | collection set | parenthesized expression;

unary = ["not"], atom;
and = unary, ["and", unary];
or = and, ["or", and];

expression = or;
```

In simple terms this means you can use the `favorite` (unused), `landscape`, `portrait` and `square`
predicates to write a logical expression for filtering photos. You can use the `()`, `not`, `and`, and `or`
operators to build your expression (listed in decreasing order of precedence). To filter by collection,
use `{<identifier 1> <identifier 2> ...}`. A photo will only be picked if it belongs to one of the given
collections. The `true` and `false` literals are also available.

Example: `portrait and (favorite or not {phone_pics family_pics})`

If you simply want to allow all photos use: `true`

#### Order options

- `SHUFFLE`: Cycle through images in a random order. After all images have been displayed once,
restart in a different random order.
- `CHRONOLOGICAL_DESCENDING` and `CHRONOLOGICAL_ASCENDING`: Cycle through images in descending or ascending capture date.
After all images have been displayed once, restart the cycle. Images without a capture date in their metadata are ignored.

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
