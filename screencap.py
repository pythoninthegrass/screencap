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

import shlex
import sys
from pathlib import Path
from sh import ErrorReturnCode, getwindowid, osascript, screencapture


def get_screenshot_dir():
    """Get the screenshot directory from config or default to ~/Desktop."""
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        from decouple import Config, RepositoryEnv

        config = Config(RepositoryEnv(env_file))
        screenshot_dir = config("SCREENSHOT_DIR", default="~/Desktop")
    else:
        from decouple import config

        screenshot_dir = config("SCREENSHOT_DIR", default="~/Desktop")

    screenshot_path = Path(screenshot_dir).expanduser()
    screenshot_path.mkdir(parents=True, exist_ok=True)

    return screenshot_path


def get_visible_apps():
    """Get names of all visible application processes."""
    try:
        apps = osascript(
            "-e", 'tell application "System Events" to get name of every application process whose visible is true'
        ).strip()

        apps_list = [app.strip() for app in apps.split(',')]
        return apps_list
    except Exception as e:
        print(f"Error getting visible applications: {e}")
        return []


def find_matching_apps(apps, pattern):
    """Find apps matching the given pattern (case-insensitive)."""
    pattern_lower = pattern.lower()
    return [app for app in apps if pattern_lower in app.lower()]


def get_window_info(app_name):
    """Get window information for the specified application."""
    print(f"=== Checking windows for \"{app_name}\" ===")

    names_to_try = [app_name]
    if app_name.lower() != app_name:
        names_to_try.append(app_name.lower())
    if app_name.capitalize() != app_name:
        names_to_try.append(app_name.capitalize())
    if app_name.upper() != app_name:
        names_to_try.append(app_name.upper())

    windows = []
    for name in names_to_try:
        try:
            print(f"Trying application name: \"{name}\"")
            output = getwindowid(name, "--list", _ok_code=[0, 1])

            if output.strip():
                for line in output.strip().split('\n'):
                    if line:
                        windows.append(line)
                if windows:
                    print("Found windows:")
                    for w in windows:
                        print(w)
                    return windows
        except ErrorReturnCode:
            continue

    if not windows:
        print(f"No windows found for \"{app_name}\".")
    return windows


def capture_screenshot(window_id, window_title=None, output_file=None):
    """Capture a screenshot of the specified window."""
    if not output_file:
        from datetime import datetime

        timestamp = datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%-I.%M.%S %p")

        if window_title:
            clean_title = window_title.replace("/", "-").replace(":", "-").strip()
            filename = f"Screenshot {clean_title} {date_str} at {time_str}.png"
        else:
            filename = f"Screenshot {date_str} at {time_str}.png"

        screenshot_dir = get_screenshot_dir()
        output_file = screenshot_dir / filename
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
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(0)

    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        visible_apps = get_visible_apps()
        print("Visible applications:")
        for app in sorted(visible_apps):
            print(f"  {app}")
        sys.exit(0)

    try:
        cmd_line = ' '.join(sys.argv[1:])
        args = shlex.split(cmd_line)
    except ValueError as e:
        print(f"Error parsing arguments: {e}")
        sys.exit(1)

    auto_select = False

    while args and args[0].startswith('--'):
        flag = args[0]
        args = args[1:]

        if flag == "--auto":
            auto_select = True
        else:
            print(f"Unknown flag: {flag}")
            sys.exit(1)

    if not args:
        print("Error: Missing app name")
        sys.exit(1)

    if len(args) > 1 and '.' in args[-1] and ' ' not in args[-1]:
        search_pattern = args[0] if len(args) == 2 else ' '.join(args[:-1])
        output_file = args[-1]
    else:
        search_pattern = args[0] if len(args) == 1 else ' '.join(args)
        output_file = None

    direct_windows = get_window_info(search_pattern)
    all_windows = []

    if direct_windows:
        for window in direct_windows:
            if window:
                all_windows.append((search_pattern, window))
        print(f"Found windows for \"{search_pattern}\"")
    else:
        visible_apps = get_visible_apps()

        if not visible_apps:
            print("No visible applications found.")
            sys.exit(1)

        matched_apps = find_matching_apps(visible_apps, search_pattern)

        if not matched_apps:
            print(f"No matching applications found for \"{search_pattern}\".")
            sys.exit(1)

        print("Matched applications:")
        for app in matched_apps:
            print(app)

        for app in matched_apps:
            windows = get_window_info(app)
            for window in windows:
                if window:
                    all_windows.append((app, window))

    if not all_windows:
        print("No windows found to capture.")
        sys.exit(1)

    import re

    parsed_windows = []
    for app_name, window_info in all_windows:
        id_match = re.search(r'id=(\d+)', window_info)
        if not id_match:
            continue

        window_id = id_match.group(1)

        title_match = re.match(r'"([^"]*)"', window_info)
        window_title = title_match.group(1) if title_match else ""

        size_match = re.search(r'size=(\d+)x(\d+)', window_info)
        if size_match:
            width = int(size_match.group(1))
            height = int(size_match.group(2))

            is_ui_element = (
                width == 0
                or height == 0
                or (width < 300 and height < 200)
                or "\n" in window_title
                or (window_title == "" and width == height)
                or window_title in ["New Command", "New Window", "New Tab", "Open", "Close", "Save"]
            )

            if is_ui_element:
                continue

            if window_title in ["New Command", "New Window", "New Tab", "Open", "Close", "Save"]:
                continue

            has_substantial_title = window_title and " — " in window_title

            if window_title == "" and not has_substantial_title:
                continue

        parsed_windows.append({'app': app_name, 'id': window_id, 'title': window_title, 'raw': window_info})

    if not parsed_windows:
        print("Could not parse window information.")
        sys.exit(1)

    parsed_windows.sort(key=lambda w: (w['title'] == "", w['title']))

    if len(parsed_windows) == 1 or auto_select:
        selected_window = parsed_windows[0]
        if len(parsed_windows) > 1:
            print("\nAuto-selecting first window (use without --auto to choose):")
            if selected_window['title']:
                print(f"  {selected_window['app']}: {selected_window['title']}")
            else:
                print(f"  {selected_window['app']}: [No Title]")
    else:
        print(f"\nFound {len(parsed_windows)} windows:")
        for i, window in enumerate(parsed_windows, 1):
            if window['title']:
                print(f"{i}. {window['app']}: {window['title']}")
            else:
                print(f"{i}. {window['app']}: [No Title]")

        while True:
            try:
                choice = input(f"\nSelect window to capture (1-{len(parsed_windows)}) [1]: ").strip()
                if not choice:
                    choice = "1"

                choice_num = int(choice)
                if 1 <= choice_num <= len(parsed_windows):
                    selected_window = parsed_windows[choice_num - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(parsed_windows)}")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nCancelled.")
                sys.exit(0)

    app_name = selected_window['app']
    window_id = selected_window['id']

    if selected_window['title']:
        print(f"\nWindow title: {selected_window['title']}")

    print(f"Capturing screenshot of window {window_id} from {app_name}...")
    capture_screenshot(window_id, app_name, output_file)


if __name__ == "__main__":
    import platform

    if platform.system() != "Darwin":
        print("This script is intended to run on macOS only.")
        sys.exit(1)
    main()
