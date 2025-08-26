#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "python-decouple>=3.8",
#     "sh>=2.2.2",
# ]
# [tool.uv]
# exclude-newer = "2025-08-31T00:00:00Z"
# ///

"""
Find and capture screenshots of application windows.

Usage:
        screencap [--auto] <partial_app_name> [output_file]
            --auto: Automatically select the first window (no prompt)
            --list: List all visible applications
Note:
        Multi-word app names: screencap "visual studio code"
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from sh import ErrorReturnCode, getwindowid, osascript, screencapture


def help():
    print(__doc__.strip())
    sys.exit(0)


def should_filter_window(window_title, width, height):
    """Determine if a window should be filtered out based on size and title."""
    ui_elements = {"New Command", "New Window", "New Tab", "Open", "Close", "Save"}
    return (
        width == 0
        or height == 0
        or (width < 300 and height < 200)
        or window_title in ui_elements
        or "\n" in window_title
        or (window_title == "" and width == height)
        or (window_title == "" and " — " not in window_title)
    )


def get_screenshot_dir():
    """Get the screenshot directory from config or default to ~/Desktop."""
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        from decouple import Config, RepositoryEnv

        config = Config(RepositoryEnv(env_file))
    else:
        from decouple import config
    screenshot_path = Path(config("SCREENSHOT_DIR", default="~/Desktop")).expanduser()
    screenshot_path.mkdir(parents=True, exist_ok=True)
    return screenshot_path


def get_visible_apps():
    """Get names of all visible application processes."""
    try:
        apps = osascript(
            "-e", 'tell application "System Events" to get name of every application process whose visible is true'
        ).strip()
        return [app.strip() for app in apps.split(',')]
    except Exception as e:
        print(f"Error getting visible applications: {e}")
        return []


def find_matching_apps(apps, search_pattern):
    """Find apps that match the search pattern using fuzzy matching."""
    search_lower = search_pattern.lower()
    return (
        [app for app in apps if app.lower() == search_lower]
        or sorted([app for app in apps if search_lower in app.lower()], key=lambda x: (x.lower().find(search_lower), len(x)))
        or sorted([app for app in apps if all(word in app.lower() for word in search_lower.split())], key=lambda x: len(x))
    )


def get_app_name_variations(app_name):
    """Generate common variations of an app name for matching."""
    return list(dict.fromkeys([app_name, app_name.lower(), app_name.capitalize(), app_name.upper(), app_name.title()]))


def try_get_windows(name):
    """Attempt to get windows for a specific app name."""
    try:
        print(f"Trying application name: \"{name}\"")
        output = getwindowid(name, "--list", _ok_code=[0, 1])
        if output.strip():
            windows = [line for line in output.strip().split('\n') if line]
            if windows:
                print("Found windows:")
                [print(w) for w in windows]
                return windows
    except ErrorReturnCode:
        pass
    return []


def get_window_info(app_name, visible_apps=None):
    """Get window information for the specified application."""
    print(f"=== Checking windows for \"{app_name}\" ===")

    # Try exact name variations first
    name_variations = get_app_name_variations(app_name)

    for name in name_variations:
        if windows := try_get_windows(name):
            return windows

    # Try fuzzy matches if no exact matches found
    if visible_apps:
        matched_apps = find_matching_apps(visible_apps, app_name)
        for matched_app in matched_apps:
            if matched_app.lower() != app_name.lower():
                print(f"Trying fuzzy match: \"{matched_app}\"")
                if windows := try_get_windows(matched_app):
                    return windows

    print(f"No windows found for \"{app_name}\".")
    return []


def generate_screenshot_filename(window_title, timestamp):
    """Generate a clean filename for the screenshot."""
    clean_title = window_title.translate(str.maketrans({"/": "-", ":": "-"})).strip() if window_title else ""
    title_part = f"{clean_title} " if clean_title else ""
    return f"Screenshot {title_part}{timestamp.strftime('%Y-%m-%d')} at {timestamp.strftime('%-I.%M.%S %p')}.png"


def parse_window_info(window_info):
    """Parse a single window info string into structured data."""
    id_match = re.search(r'id=(\d+)', window_info)
    if not id_match:
        return None

    window_id = id_match.group(1)
    title_match = re.match(r'"([^"]*)"', window_info)
    window_title = title_match.group(1) if title_match else ""

    width = height = 0
    if size_match := re.search(r'size=(\d+)x(\d+)', window_info):
        width, height = int(size_match.group(1)), int(size_match.group(2))

    return {'id': window_id, 'title': window_title, 'width': width, 'height': height, 'raw': window_info}


def capture_screenshot(window_id, window_title=None, output_file=None):
    """Capture a screenshot of the specified window."""
    output_file = (
        Path(output_file) if output_file else get_screenshot_dir() / generate_screenshot_filename(window_title, datetime.now())
    )
    try:
        screencapture("-l", window_id, str(output_file))
        print(f"Screenshot saved to: {output_file}")
        return True
    except ErrorReturnCode as e:
        print(f"Error capturing screenshot: {e}")
        return False


def main():
    import platform
    from textwrap import dedent

    if platform.system() != "Darwin":
        print("This script is intended to run on macOS only.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Find and capture screenshots of application windows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent("""
            Examples:
              screencap Firefox
              screencap --auto Terminal
              screencap "Visual Studio Code"
              screencap --auto TextEdit ~/screenshot.png
              screencap --list

            Note: Multi-word app names should be quoted.
            """).strip(),
    )

    parser.add_argument('app_name', nargs='?', help='Partial application name to search for')
    parser.add_argument('output_file', nargs='?', help='Output file path (optional)')
    parser.add_argument('--auto', action='store_true', help='Automatically select the first window (no prompt)')
    parser.add_argument('--list', action='store_true', help='List all visible applications')

    args = parser.parse_args()

    if args.list:
        print("Visible applications:")
        [print(f"  {app}") for app in sorted(get_visible_apps())]
        sys.exit(0)

    if not args.app_name:
        parser.error("Missing app name")

    search_pattern, output_file, auto_select = args.app_name, args.output_file, args.auto

    visible_apps = get_visible_apps()
    if not visible_apps:
        print("No visible applications found.")
        sys.exit(1)

    all_windows = [(search_pattern, w) for w in get_window_info(search_pattern, visible_apps) if w]
    if all_windows:
        print(f"Found windows for \"{search_pattern}\"")
    else:
        matched_apps = find_matching_apps(visible_apps, search_pattern)

        if not matched_apps:
            print(f"No matching applications found for \"{search_pattern}\".")
            sys.exit(1)

        print(f"Found matching applications for \"{search_pattern}\":")

        [
            print(f"  {app}") or all_windows.extend((app, w) for w in get_window_info(app, visible_apps) if w)
            for app in matched_apps
        ]

    if not all_windows:
        print("No windows found to capture.")
        sys.exit(1)

    parsed_windows = [
        {**parsed, 'app': app_name}
        for app_name, window_info in all_windows
        if (parsed := parse_window_info(window_info)) is not None
        and not should_filter_window(parsed['title'], parsed['width'], parsed['height'])
    ]

    if not parsed_windows:
        print("Could not parse window information.")
        sys.exit(1)
    parsed_windows.sort(key=lambda w: (w['title'] == "", w['title']))
    if len(parsed_windows) == 1 or auto_select:
        selected_window = parsed_windows[0]
        if len(parsed_windows) > 1:
            print("\nAuto-selecting first window (use without --auto to choose):")
            print(f"  {selected_window['app']}: {selected_window['title'] or '[No Title]'}")
    else:
        print(f"\nFound {len(parsed_windows)} windows:")
        [print(f"{i}. {window['app']}: {window['title'] or '[No Title]'}") for i, window in enumerate(parsed_windows, 1)]

        while True:
            try:
                choice = input(f"\nSelect window to capture (1-{len(parsed_windows)}) [1]: ").strip() or "1"
                choice_num = int(choice)
                if 1 <= choice_num <= len(parsed_windows):
                    selected_window = parsed_windows[choice_num - 1]
                    break
                print(f"Please enter a number between 1 and {len(parsed_windows)}")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nCancelled.")
                sys.exit(0)

    if selected_window['title']:
        print(f"\nWindow title: {selected_window['title']}")

    print(f"Capturing screenshot of window {selected_window['id']} from {selected_window['app']}...")

    capture_screenshot(selected_window['id'], selected_window['app'], output_file)


if __name__ == "__main__":
    main()
