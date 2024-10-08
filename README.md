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
- [Cru](#cru): Image metadata loader

## Encre

*Convert images to an e-ink display palette.*

This is an optional component. If you're not using an e-ink display, you can instead
use Affiche with a custom display writer script, see [below](#affiche).

Encre process read a wide variety of image formats (any supported by your libvips install).
It performs lightness adjustments and perceptual gamut mapping, and finally dithers to
the e-ink display palette. The final byte buffer can be sent to the display hardware.

A [command line tool](encre/cli/src/main.cpp), and both a [C++](encre/core/include/encre.hpp)
and a [Python API](encre/py/src/py_encre.cpp), are available.

Samples results are available in [test_data](encre/test_data).
They were generated for a 7.3" Pimoroni Inky Impression. Keep in mind that
current colour e-ink display technology has rather low gamut, so it's
normal that the images look washed out. That's what it looks like on the
actual display. This tool focuses on accurate colour mapping, it can't
do miracles.

### Build

- Install pkg-config
- Install Python (3.9 or newer)
- Install libvips (8.15.1 or newer)
- Run `cmake --workflow --preset release`

Other dependencies are installed by Vcpkg.

You might have to upgrade CMake, Python or your C++ compiler, the logs should tell you.

There are additional notes [here](encre/rpi_build_notes.txt) specific for Raspberry Pi users.

### Running

If the build succeeds, you can use the CLI tool at `build/release/cli/encre-cli` to
test image conversions. For example: `build/release/cli/encre-cli test_data/colors.png -p`
will output `test_data/colors.bin` (palette'd image as raw unsigned bytes) and
`test_data/colors_preview.png` as a preview. Run with `-h` for more information.

If you have one of the displays listed [below](#supported-displays), you can use
[write_to_display.py](encre/display/write_to_display.py) to directly write an image to the display.
Pass the display name as the first argument.

### Supported displays

- [Pimoroni Inky Impression](https://shop.pimoroni.com/products/inky-impression-7-3):
    - Install [requirements-pimoroni_inky](affiche/requirements-pimoroni_inky.txt)
    - Use name "pimoroni_inky"
- [Good Display E6 7.3" display (GDEP073E01)](https://buyepaper.com/products/gdep073e01)
    - Install [requirements-GDEP073E01](affiche/requirements-GDEP073E01.txt).
    - Use name "GDEP073E01"
- Simulated
    - Use name "simulated"
    - No additional requirements
    - Useful for testing, but does nothing

#### Other display

If your display isn't in this list, we're open to contributions!

Implement the [`Display`](encre/display/display_protocol.py) protocol.
You can looks at [`GDEP073E01.py`](encre/display/GDEP073E01.py) for an example.

To create a custom palette, call `py_encre.make_palette_xyz` or `py_encre.make_palette_lab`.
If you're lucky, your display data sheet will have the CIE Lab values for each colour,
otherwise you can eyeball them... An example is available [here](encre/misc/rgb_palette_example.py).

### Options

Options are available to tweak the image processing. Operations
are performed in the [Oklab](https://bottosson.github.io/posts/oklab/)
perceptual colour space.

- Rotation: apply a rotation (after the EXIF orientation, if applicable)
    - Automatic: landscape is unchanged, portrait is rotated to landscape.
    - Landscape: unchanged
    - Portrait: 90° counter-clockwise
    - Landscape upside-down: 180°
    - Portrait upside-down: 90° clockwise
- Dynamic range: percentage of the original image dynamic range to be
rescaled into the output palette. Using `0` will keep the original dynamic
range, which will lead to a lot of clipping if the palette has a small
dynamic range. Using `1` will force the entirety of the dynamic range
into the output, which means no clipping, but lowest contrast possible.
- Exposure: Lightness scale factor (multiply with `L` component). If not specified,
then some basic automatic exposure adjustment is made to bring the image
dynamic range into the output palette.
- Brightness: Lightness bias factor (add to `L` component). If not specified,
then some basic automatic brightness adjustment is made to bring the image
dynamic range into the output palette.
- Contrast: Slope of the sigmoid function used to compress the image dynamic
range into the output palette. Larger values increase contrat in the mid range,
at the cost of compressing the shadows and highlights.
- Sharpening: edge sharpening, useful to recover some details after the resize.
- Clipped chroma recovery: α value described [here](https://bottosson.github.io/posts/gamutclipping/#adaptive-%2C-hue-independent),
used to recover some color from the clipped highlights caused by gamut mapping.
- Dither error attenuation: exponential attenuation factor applied to the dither
error before diffusion. Helps reduce smearing caused by small errors being
diffused over large areas, but comes at the cost of colour accuracy.
Values over `1` create a more artistic effect.

Options are also defined in [encre_options.json](encre/encre_options.json) for use by Affiche.

## Affiche

*Local web interface*

After building [Encre](#encre), create a Python virtual environment, and install the
[requirements](affiche/requirements.txt) using `pip`.

Start the server using `start.sh`. Use `stop.sh` if you need to stop the server when it's running
in the background. You might need to change system settings to make port `80` available without
privileges. The simplest solution is to run `sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80`.

The server should be available at the host's LAN address on port `80`.

If you want image metadata support (EXIF information and geolocation), you need to build [Cru](#cru).

[<img src="images/affiche_screenshot.png" width="400"/>](images/affiche_screenshot.png)

### Configuration

Copy the [default config](affiche/default_config.json) and name it `config.json`.
In this file you can overwrite the following fields:
- `TEMP_PATH`: Where to write the temporary files, absolute or relative to the server executable
- `DISPLAY_WRITER_COMMAND`: The command line to run for writing a new image to the display as a list of arguments.
As well as the image path, it must accept the `--options <json>` and `--preview <path>` arguments to pass in the
options and the preview image output path.
- `DISPLAY_WRITER_OPTIONS_SCHEMA_PATH`: Path to the options schema for the display writer.
See [encre_options.json](encre/encre_options.json) for an example.
- `DISPLAY_WRITER_OPTIONS`: Dictionary of option name and default value override.
For example: `{"dynamic_range": 0.8}`.
- `MAP_TILES`: URL and options for [Leaflet `L.tileLayer()` constructor](https://leafletjs.com/reference.html#tilelayer-l-tilelayer).
Lets you customize the map shown by Affiche. If you want an English map, I recommend the
[Thunderforest Atlas tiles](https://www.thunderforest.com/maps/atlas/) (free account required to obtain an API key).
- `EXPO_ADDRESS`: Hostname and optional port suffix for the Expo server. Must be externally reachable (i.e.: `affiche.local` instead
of `localhost`). Optional, can be `null` to disable Expo integration. If empty, then default to the local machine network name.

### Tips & Help

#### You want Affiche (and Expo) to start automatically when the server boots

You can use Cron to launch on boot. Edit the user's crontab using `crontab -e` and add
`@reboot cd ~/Cadre/affiche && bash start.sh; cd ~/Cadre/expo && bash start.sh`
(skip the part after `;` if you're not using Expo). You will need to use `bash -l` if
you have environment variables required by Affiche (or Expo) in your bash profile
(such as if you followed the Encre Raspberry Pi build instructions).

#### The connection to your Raspberry Pi is unreliable, especially when using the `.local` address

Try disabling Wifi power management using `iwconfig wlan0 power off`. You can make this change
persistent on reboot by adding `/sbin/iwconfig wlan0 power off` to `/etc/rc.local`.

#### The Expo link is wrong

More specifically, your local address is `cadre.local`, and clicking the Expo link opens `cadre`,
which fails to resolve.

Make sure that you have the `.local` address in the `/etc/hosts` file, and that it appears before the hostname.
For example: `127.0.1.1	cadre.local cadre`

##  Expo

*Automatic photo update service*

This is an optional component. It's a separate service which maintains a database of photos locations and metadata,
and periodically posts one to Affiche.

Create a Python virtual environment, and install the [requirements](expo/requirements.txt) using `pip`.
Additional requirements are also needed for the following features:
- `FileSystemCollection`: [Cru](#cru)
- `AmazonPhotosCollection`: [requirements-azp](expo/requirements-azp.txt)

Start the server using `start.sh`. Use `stop.sh` if you need to stop the server when it's running in the background.

The server should be available at the host's LAN address on port `21110`.
You can run Expo on the same host as Affiche or a different one.

[<img src="images/expo_screenshot.png" width="400"/>](images/expo_screenshot.png)

### Configuration

Copy the [default config](affiche/default_config.json) and name it `config.json`.
In this file you can overwrite the following fields:
- `DB_PATH`: where to write the Expo persistent data, absolute or relative to the server executable

### Collections

List all collections by `GET`ing from `/collections`.
Create a collection by `PUT`ting to `/collections` a JSON object like so:
```jsonc
{
    "identifier": "my_collection",
    "display_name": "My Collection",
    "schedule": "*/5 * * * *",
    "enabled": true,
    "class_name": "FileSystemCollection",
    "settings": {
        // See below
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

Use this to display photos from a local collection such as a NAS. You can also create an SMB share on a Raspberry Pi
where you upload your favourite photos. The photos must be visible on the filesystem where Expo is running.

Requires [Cru](#cru) to process images. Scan the `root_path` for known image formats.

Does not support the `favorite` filter.

Settings:
```jsonc
{
    "root_path": "<path to your local photos folder>"
}
```

#### AmazonPhotosCollection

Uses an unofficial [Amazon Photos Python API](https://github.com/trevorhobenshield/amazon_photos) by
[Trevor Hobenshield](https://github.com/trevorhobenshield) (actually [a fork](https://github.com/DDoS/amazon_photos)
with a few improvements).

Settings:
```jsonc
{
    "user_agent": "<User agent string from the browser used to login to Amazon Photos>",
    "cookies": {
        // Copy cookies here as a dictionary. It's not known exactly which cookies are required,
        // if you're missing some you might eventually get an authentication error.
        // This list just an example, since the cookie names are region specific (amazon.ca shown).
        // See: https://github.com/trevorhobenshield/amazon_photos?tab=readme-ov-file#setup
        "at-acbca": "***",
        "ubid-acbca": "***",
        "sess-at-acbca": "***",
        "sst-acbca": "***",
        "x-acbca": "***",
        "lc-acbca": "***",
        "session-id": "***",
        "session-id-time": "***"
    }
}
```

### Scan

Immediately trigger a collection scan by `POST`ing to `/scan` a JSON object like so:
```jsonc
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
```jsonc
{
    "identifier": "my_schedule",
    "display_name": "My Schedule",
    "hostname": "<Affiche hostname>",
    "schedule": "*/20 * * * *",
    "enabled": true,
    "filter": "<filter expression>",
    "order": "<order enum name>",
    "affiche_options": {
        // Example for Encre
        "contrast": 0.5,
        "sharpening": 2
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
- `affiche_options` is optional, override the default options for the target Affiche instance

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
```jsonc
{
    "identifier": "<schedule identifier>",
    "delay": 0
}
```
- `identifier` is a schedule identifier
- `delay` a delay in seconds (float), is optional and defaults to `0`

## Cru

Cru is a native Python module for quickly loading image metadata, like resolution and tags.
It also does some processing and pretty formatting for easier consumption.

### Build

- Follow the Encre build instructions first, that'll make sure you have everything installed
- Run `cmake --workflow --preset release`

### Running

The filesystem collection should automatically detect and import the module.
If you see "Cru module not found" in the logs, check that the module can be
indeed be loaded from `<repo path>/cru/build/release` by Python.
