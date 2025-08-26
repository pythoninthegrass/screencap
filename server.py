#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "fastmcp>=2.11.3",
#     "httpx-sse>=0.4.0",
#     "httpx>=0.27.0,<1.0",
#     "python-decouple>=3.8",
#     "sh>=2.2.2",
# ]
# [tool.uv]
# exclude-newer = "2025-08-31T00:00:00Z"
# ///

"""
FastMCP server for screencap functionality.

Provides screenshot tools for macOS application windows via MCP.
"""

import asyncio
import platform
import signal
import sys
import os
from datetime import datetime
from fastmcp import FastMCP
from pathlib import Path
from contextlib import redirect_stdout

# Import the main screencap functions
from screencap import (
    find_matching_apps,
    generate_screenshot_filename,
    get_screenshot_dir,
    get_visible_apps,
    parse_window_info,
    should_filter_window,
)

# Create MCP-specific versions that suppress output
def mcp_get_window_info(app_name, visible_apps=None):
    """Get window information with output suppressed for MCP."""
    from screencap import get_window_info
    with redirect_stdout(open(os.devnull, 'w')):
        return get_window_info(app_name, visible_apps)

def mcp_capture_screenshot(window_id, window_title=None, output_file=None):
    """Capture screenshot with output suppressed for MCP."""
    from screencap import capture_screenshot
    with redirect_stdout(open(os.devnull, 'w')):
        return capture_screenshot(window_id, window_title, output_file)

# Ensure macOS only
if platform.system() != "Darwin":
    raise RuntimeError("screencap MCP server only works on macOS")

# Create the FastMCP server
mcp = FastMCP(name="screencap", instructions="Screenshot capture tools for macOS applications")

# Global flag for shutdown
shutdown_event = asyncio.Event()
_sigint_count = 0

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    global _sigint_count

    if signum == signal.SIGINT:
        _sigint_count += 1
        if _sigint_count == 1:
            print(f"\nReceived SIGINT, shutting down gracefully... (Press Ctrl+C again to force)")
            shutdown_event.set()

            # Force exit after 2 seconds if still hanging
            def force_exit():
                import time
                time.sleep(2)
                if _sigint_count == 1:
                    print("Force exiting...")
                    import os
                    os._exit(0)

            import threading
            threading.Thread(target=force_exit, daemon=True).start()
        else:
            print("\nForce exiting immediately...")
            import os
            os._exit(1)
    elif signum == signal.SIGTERM:
        print("\nReceived SIGTERM, shutting down gracefully...")
        shutdown_event.set()
        import os
        os._exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
# Note: SIGTSTP (Ctrl+Z) cannot be reliably overridden, so we don't handle it


@mcp.tool
def list_apps() -> list[str]:
    """List all visible application names."""
    return sorted(get_visible_apps())


@mcp.tool
def screenshot_app(app_name: str, auto_select: bool = False, output_file: str = None) -> dict:
    """
    Capture a screenshot of an application window.

    Args:
        app_name: Application name or partial name to search for
        auto_select: Automatically select first matching window (default: False)
        output_file: Optional custom output file path

    Returns:
        Dictionary with success status, window info, and output file path
    """
    try:
        visible_apps = get_visible_apps()
        if not visible_apps:
            return {"error": "No visible applications found"}

        # Try to find windows for the app
        all_windows = [(app_name, w) for w in mcp_get_window_info(app_name, visible_apps) if w]

        # If no direct match, try fuzzy matching
        if not all_windows:
            matched_apps = find_matching_apps(visible_apps, app_name)
            if matched_apps:
                all_windows = [(app, w) for app in matched_apps for w in mcp_get_window_info(app, visible_apps) if w]

        if not all_windows:
            return {"error": f"No windows found for '{app_name}'"}

        # Parse and filter windows
        parsed_windows = [
            {**parsed, 'app': app}
            for app, window_info in all_windows
            if (parsed := parse_window_info(window_info)) is not None
            and not should_filter_window(parsed['title'], parsed['width'], parsed['height'])
        ]

        if not parsed_windows:
            return {"error": "No valid windows found after filtering"}

        # Sort windows (empty titles last, but preserve original order otherwise)
        parsed_windows.sort(key=lambda w: (w['title'] == ""))

        # Auto-select or return choices
        if auto_select or len(parsed_windows) == 1:
            selected_window = parsed_windows[0]
        else:
            return {
                "choices": [
                    {"id": i, "app": w['app'], "title": w['title'] or '[No Title]', "size": f"{w['width']}x{w['height']}"}
                    for i, w in enumerate(parsed_windows)
                ],
                "message": "Multiple windows found. Use auto_select=true to select the first one automatically.",
            }

        # Capture screenshot
        timestamp = datetime.now()
        if output_file:
            output_path = Path(output_file)
        else:
            output_path = get_screenshot_dir() / generate_screenshot_filename(selected_window['app'], timestamp)

        success = mcp_capture_screenshot(selected_window['id'], selected_window['app'], str(output_path))

        return {
            "success": success,
            "window": {
                "app": selected_window['app'],
                "title": selected_window['title'] or '[No Title]',
                "id": selected_window['id'],
                "size": f"{selected_window['width']}x{selected_window['height']}",
            },
            "output_file": str(output_path),
        }

    except Exception as e:
        return {"error": f"Screenshot failed: {str(e)}"}


@mcp.tool
def screenshot_by_choice(app_name: str, choice_id: int, output_file: str = None) -> dict:
    """
    Capture screenshot by selecting a specific window choice from previous query.

    Args:
        app_name: Application name used in the original query
        choice_id: Window choice ID from the choices list
        output_file: Optional custom output file path
    """
    try:
        # Get windows again (could be cached in real implementation)
        visible_apps = get_visible_apps()
        all_windows = [(app_name, w) for w in mcp_get_window_info(app_name, visible_apps) if w]

        if not all_windows:
            matched_apps = find_matching_apps(visible_apps, app_name)
            if matched_apps:
                all_windows = [(app, w) for app in matched_apps for w in mcp_get_window_info(app, visible_apps) if w]

        parsed_windows = [
            {**parsed, 'app': app}
            for app, window_info in all_windows
            if (parsed := parse_window_info(window_info)) is not None
            and not should_filter_window(parsed['title'], parsed['width'], parsed['height'])
        ]

        if not parsed_windows or choice_id >= len(parsed_windows):
            return {"error": f"Invalid choice ID {choice_id}"}

        selected_window = parsed_windows[choice_id]

        # Capture screenshot
        timestamp = datetime.now()
        if output_file:
            output_path = Path(output_file)
        else:
            output_path = get_screenshot_dir() / generate_screenshot_filename(selected_window['app'], timestamp)

        success = mcp_capture_screenshot(selected_window['id'], selected_window['app'], str(output_path))

        return {
            "success": success,
            "window": {
                "app": selected_window['app'],
                "title": selected_window['title'] or '[No Title]',
                "id": selected_window['id'],
                "size": f"{selected_window['width']}x{selected_window['height']}",
            },
            "output_file": str(output_path),
        }

    except Exception as e:
        return {"error": f"Screenshot failed: {str(e)}"}


if __name__ == "__main__":
    try:
        mcp.run()
    except (KeyboardInterrupt, SystemExit):
        pass
