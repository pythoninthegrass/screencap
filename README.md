# screencap

Use AppleScript (`osascript`) with `getwindowid` to find open windows and take screenshots of them on macOS devices.

Python implementation of John Maeda's [bash solution](https://maeda.pm/2024/11/16/macos-screen-capture-via-cli/).

## Minimum Requirements

* [Python 3.13](https://www.python.org/downloads/release/python-3130/)
* [uv](https://docs.astral.sh/uv/)

## Recommended Requirements

[mise](https://mise.jdx.dev/getting-started.html)

## Quickstart

Direct commands:

```bash
# Basic usage
./screencap.py Firefox

# Auto-select first window
./screencap.py --auto Terminal

# Multi-word app names
./screencap.py "Visual Studio Code"

# List visible applications
./screencap.py --list

# Custom output file
./screencap.py --auto TextEdit ~/screenshot.png
```

Symlink to somewhere in the path

```bash
# full name
ln -s $(pwd)/screencap.py ~/.local/bin/screencap

# shorthand
ln -s $(pwd)/screencap.py ~/.local/bin/sc

# call via symlink
λ sc
Installed 2 packages in 2ms
Find and capture screenshots of application windows.

Usage:
        screencap [--auto] <partial_app_name> [output_file]
...
```

## TODO

Outstanding tasks are located in [TODO.md](TODO.md).

## Further Reading

* [Script to Hide Apps - Scripting Forums / AppleScript | Mac OS X - MacScripter](https://www.macscripter.net/t/script-to-hide-apps/20522/6)
