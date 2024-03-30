# Cru

Cru is a small native Python module for quickly identifying raw format images.
It's only necessary because libvips lacks proper raw image support: it delegates
to ImageMagick, which always loads the whole image, and takes forever to finish.

If you're not using raw formats (like CR3), you can ignore this.

## Build

- Follow the Encre build instructions first,
that'll make sure you have everything installed
- Run `cmake --workflow --preset release`

## Running

The filesystem collection should automatically detect and import the module.
If you see "Cru module not found" in the logs, check that the module can be
indeed be loaded from `<repo path>/expo/cru/build/release` by Python.
