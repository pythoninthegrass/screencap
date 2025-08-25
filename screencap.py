#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.13,<3.14"
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
    # Filter zero-size windows
    if width == 0 or height == 0:
        return True

    # Filter small windows (likely UI elements)
    if width < 300 and height < 200:
        return True

    # Filter UI elements and system dialogs
    ui_elements = {"New Command", "New Window", "New Tab", "Open", "Close", "Save"}
    if window_title in ui_elements or "\n" in window_title:
        return True

    # Filter empty square windows (likely system UI)
    if window_title == "" and width == height:
        return True

    # Filter empty titles without proper content indicators
    return window_title == "" and " — " not in window_title


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
    exact_matches = [app for app in apps if app.lower() == search_lower]
    if exact_matches:
        return exact_matches

    partial_matches = [app for app in apps if search_lower in app.lower()]
    if partial_matches:
        return sorted(partial_matches, key=lambda x: (x.lower().find(search_lower), len(x)))

    word_matches = []
    search_words = search_lower.split()
    for app in apps:
        app_lower = app.lower()
        if all(word in app_lower for word in search_words):
            word_matches.append(app)

    return sorted(word_matches, key=lambda x: len(x))


def get_app_name_variations(app_name):
    """Generate common variations of an app name for matching."""
    variations = [
        app_name,               # Original
        app_name.lower(),       # lowercase
        app_name.capitalize(),  # First letter capitalized
        app_name.upper(),       # UPPERCASE
        app_name.title(),       # Title Case
    ]
    # Remove duplicates while preserving order
    return list(dict.fromkeys(variations))


def try_get_windows(name):
    """Attempt to get windows for a specific app name."""
    try:
        print(f"Trying application name: \"{name}\"")
        output = getwindowid(name, "--list", _ok_code=[0, 1])
        if output.strip():
            windows = [line for line in output.strip().split('\n') if line]
            if windows:
                print("Found windows:")
                for w in windows:
                    print(w)
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
    clean_title = window_title.replace("/", "-").replace(":", "-").strip() if window_title else "Window"

    date_str = timestamp.strftime('%Y-%m-%d')
    time_str = timestamp.strftime('%-I.%M.%S %p')

    return f"Screenshot {clean_title} {date_str} at {time_str}.png"


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
    if not output_file:
        timestamp = datetime.now()
        filename = generate_screenshot_filename(window_title, timestamp)
        output_file = get_screenshot_dir() / filename
    else:
        output_file = Path(output_file)
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
        for app in sorted(get_visible_apps()):
            print(f"  {app}")
        sys.exit(0)

    if not args.app_name:
        parser.error("Missing app name")

    search_pattern = args.app_name
    output_file = args.output_file
    auto_select = args.auto

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
        for app in matched_apps:
            print(f"  {app}")
            all_windows.extend((app, w) for w in get_window_info(app, visible_apps) if w)
    if not all_windows:
        print("No windows found to capture.")
        sys.exit(1)

    parsed_windows = []
    for app_name, window_info in all_windows:
        if parsed := parse_window_info(window_info):
            parsed['app'] = app_name
            if not should_filter_window(parsed['title'], parsed['width'], parsed['height']):
                parsed_windows.append(parsed)

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
        for i, window in enumerate(parsed_windows, 1):
            print(f"{i}. {window['app']}: {window['title'] or '[No Title]'}")
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
