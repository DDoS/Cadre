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
They were generated for a 7.3" Spectra 6 E-ink display. Keep in mind that
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
[write_to_display.py](#display-writer-script) to directly write an image to the display.
Pass the display name as the first argument. Some displays have additional options which can be
set using `--display-config <json>`.

### Supported displays

- [Pimoroni Inky Impression](https://github.com/pimoroni/inky?tab=readme-ov-file#inky-impression):
    - Name: `pimoroni_inky`
    - Install [requirements-pimoroni_inky](affiche/requirements-pimoroni_inky.txt).
    - Follow the Raspberry Pi configuration instructions in the official repo
    [README](https://github.com/pimoroni/inky?tab=readme-ov-file#install-stable-library-from-pypi-and-configure-manually).
    - If you're using the 7.3" inch model, I recommend using the `AC073TC1` display below.
    The Pimoroni library isn't great...
- Generic E-Ink 7.3" Gallery Palette display (AC073TC1)
    - Name: `AC073TC1`
    - Install [requirements-spi](affiche/requirements-spi.txt).
    - Enable SPI0 with CS0 (default).
    - Compatible with the Inky Impression 7.3" and other similar displays.
    - Check the [source file](encre/display/AC073TC1.py) for the pinout.
- [Good Display E6 7.3" display (GDEP073E01)](https://buyepaper.com/products/gdep073e01)
    - Name: `GDEP073E01`
    - Install [requirements-spi](affiche/requirements-spi.txt).
        - If you run into a build error regarding `lgpio`, follow the install instructions [here](https://abyz.me.uk/lg/download.html)
    - Enable SPI0 with CS0 (default).
    - Check the [source file](encre/display/GDEP073E01.py) for the pinout.
- [Waveshare 13.3inch e-Paper (E)](https://www.waveshare.com/13.3inch-e-paper-hat-plus-e.htm?sku=29353)
    - Name: `EL133UF1`
    - Install [requirements-spi](affiche/requirements-spi.txt).
        - If you run into a build error regarding `lgpio`, follow the install instructions [here](https://abyz.me.uk/lg/download.html)
    - Enable SPI0 but disable CS0 and CS1 (in `/boot/firmware/config.txt` add `dtoverlay=spi0-0cs`).
    - Check the [source file](encre/display/EL133UF1.py) for the pinout.
- Proxy
    - Name: `proxy`
    - Options:
        - `width`, `height`: display width and height
        - `url`: URL to post the image to
    - Write the converted image to a custom binary format defined by Encre, and post it to the URL.
    The file can then be read using the Encre API or by `write_to_display.py`. Intended for use with [Expo](#expo).
    Useful for converting an image locally on a more capable computer before posting it to an Affiche instance
    running on a less capable device. See [proxying](#proxying) for an example.
- Simulated
    - Name: `simulated`
    - Options:
        - `width`, `height`: display width and height
        - `delay`: display simulated update time in seconds
    - Useful for testing, but does nothing

#### Other displays

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
- Gray chroma tolerance: allow some chroma in the in the blacks and whites,
at the exchange of more contrast.
- Hue dependent chroma clamping: if true use the algorithm described
[here](https://bottosson.github.io/posts/gamutclipping/#adaptive-%2C-hue-dependent),
otherwise use the algorithm described
[here](https://bottosson.github.io/posts/gamutclipping/#adaptive-%2C-hue-independent).
Hue dependent typically gives better results and is the default. It's slightly slower.
- Clipped chroma recovery: α value mentioned in the hue clamping algorithms above,
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
privileges. The simplest solution is to run `sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80`
(or set `net.ipv4.ip_unprivileged_port_start=80` in `/etc/sysctl.d/50-unprivileged-ports.conf` to
make this permanent).

The server should be available at the host's LAN address on port `80`.

If you want to use a different port or hostname, then use the `-p` and `-h` arguments of `start.sh`.
When running `stop.sh` pass the same port using `-p`.

To post a picture to Affiche without the web interface, simply send it as a `multipart/form-data`
as a `file` or `url` key:
```sh
curl cadre.local -F file=@image.jpg
curl cadre.local -F url=https://upload.wikimedia.org/wikipedia/commons/7/70/African_leopard_male_%28cropped%29.jpg
```
You can also populate the "Collection" and "Path" info fields by using the `info` key:
`info='{"path":"a path", "collection": "collection name"}'`.

If you want image metadata support (EXIF information and geolocation), you need to build [Cru](#cru).

[<img src="images/affiche_screenshot.png" width="400"/>](images/affiche_screenshot.png)

### Configuration

Copy the [default config](affiche/default_config.json) and name it `config.json`.
In this file you can overwrite the following fields:
- `TEMP_PATH`: Where to write the temporary files, absolute or relative to the server executable.
- `DISPLAY_WRITER_COMMAND`: The command line for writing an image to the display. See [below](#display-writer-script).
- `DISPLAY_WRITER_OPTIONS_SCHEMA_PATH`: Path to the options schema for the display writer.
See [encre_options.json](encre/encre_options.json) for an example.
- `DISPLAY_WRITER_OPTIONS`: Dictionary of option name and default value override.
For example: `{"dynamic_range": 0.8}`. Must respect the schema from `DISPLAY_WRITER_OPTIONS_SCHEMA_PATH`.
- `MAP_TILES`: URL and options for [Leaflet `L.tileLayer()` constructor](https://leafletjs.com/reference.html#tilelayer-l-tilelayer).
Lets you customize the map shown by Affiche. If you want an English map, I recommend the
[Thunderforest Atlas tiles](https://www.thunderforest.com/maps/atlas/) (free account required to obtain an API key).
- `EXPO_ADDRESS`: Hostname and optional port suffix for the Expo server. Must be externally reachable (i.e.: `affiche.local` instead
of `localhost`). Optional, can be `null` to disable Expo integration. If empty, then default to the local machine network name.

You can override the default config path by using the `-c` argument of `start.sh` or by setting the environment variable
`AFFICHE_CONFIG_PATH` to your desired path. By default it's `./config.json`.

### Display writer script

You more than likely just want to use the default `encre/display/write_to_display.py` script. Check its `--help` output for more details.
If you need a custom display implementation, then it's recommended to [implement the `Display` protocol](#other-displays).

If you really want to use a custom script, then it must accept the following arguments (automatically populated by Affiche):
- `<image_path>`: path to the input image.
- `--options <json>`: options in the same format as `DISPLAY_WRITER_OPTIONS`.
- `--info <json>`: image info, either loaded by [Cru](#cru) or user provided.
- `--preview <path>`: output path for the web interface preview.

Furthermore if you want Affiche to display the image update progress, it should output `Status: CONVERTING` and `Status: DISPLAYING`
to `stdout` to notify of the current state.

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

#### Your Raspberry Pi stops responding to all connections until power cycled

On a lower power Raspberry Pi, like a Zero 2, it's possible that if an automatic `apt` update runs
at the same time as a large photo is being processed, the system will crash. Consider disabling the
automatic `apt` updates:
```sh
sudo systemctl mask apt-daily-upgrade
sudo systemctl mask apt-daily
sudo systemctl disable apt-daily-upgrade.timer
sudo systemctl disable apt-daily.timer
```

#### The Expo link is wrong

More specifically, your local address is `cadre.local`, and clicking the Expo link opens `cadre`,
which fails to resolve.

Make sure that you have the `.local` address in the `/etc/hosts` file, and that it appears before the hostname.
For example: `127.0.1.1	cadre.local cadre`

## Expo

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

If you want to use a different port or hostname, then use the `-p` and `-h` arguments of `start.sh`.
When running `stop.sh` pass the same port using `-p`.

[<img src="images/expo_screenshot.png" width="400"/>](images/expo_screenshot.png)

### Configuration

Copy the [default config](affiche/default_config.json) and name it `config.json`.
In this file you can overwrite the following fields:
- `DB_PATH`: where to write the Expo persistent data, absolute or relative to the server executable.
- `POST_COMMANDS`: dictionary of custom post commands that can be used by [schedules](#schedules).
Each command has an identifier (key), and a list of command line arguments (value).
The arguments can contain the placeholder `%HOSTNAME%`, which will be replaced with the hostname of the
schedule using the command. See [proxying](#proxying) for an example.

You can override the default config path by using the `-c` argument of `start.sh` or by setting the environment variable
`EXPO_CONFIG_PATH` to your desired path. By default it's `./config.json`.

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
    },
    "post_command_id": "" // Or an identifier from POST_COMMANDS in the config
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
- `post_command_id` is optional, override the default command for posting a photo to the Affiche instance

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

### Proxying

You can have Expo convert the image locally before posting it to Affiche. This is useful if you want to run Expo on a
more capable computer like a Raspberry Pi 4 or 5, and use cheaper computers like the Raspberry Pi Zero 2 for multiple
Affiche instances. Once converted, the image requires very little compute power to be displayed. There's a WIP project
to even support the Raspberry Pi Pico 2 using this mechanism.

Use the Encre `proxy` display to convert locally and post the result to an Affiche instance.
```jsonc
"POST_COMMANDS": {
    "inky": [
        "../encre/display/write_to_display.py",
        "proxy",
        "--display-config", "{\"url\": \"http://%HOSTNAME%\", \"height\": 480, \"width\": 800}",
        "--palette", "eink_spectra_6"
    ]
}
```

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
