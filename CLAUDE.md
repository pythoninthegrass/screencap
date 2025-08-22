# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**screencap** is a macOS-specific command-line tool for capturing screenshots of application windows. It uses native macOS utilities (AppleScript, screencapture) along with getwindowid to intelligently find and screenshot application windows with smart filtering of UI elements.

## Architecture

- **Self-Contained Script**: Uses uv's inline script format with dependencies embedded in `screencap.py`
- **Native Integration**: Leverages macOS system commands via the `sh` library for subprocess management
- **Smart Discovery**: Pattern-based app matching with sophisticated window filtering to exclude menus/dialogs
- **Configurable Output**: Supports custom screenshot directories via `SCREENSHOT_DIR` environment variable

## Development Commands

### Testing (Optimized Strategy)

```bash
# Fast unit tests with parallel execution (0.84s)
uv run pytest -v -m unit -n auto

# Integration tests (sequential, 10.75s) 
uv run pytest -v -m integration

# All tests
uv run pytest -v -m unit -n auto && uv run pytest -v -m integration

# Coverage
uv run pytest --cov=screencap --cov-report=html
```

### Code Quality

```bash
# Format code
ruff format .

# Check formatting
ruff format --check --diff .

# Lint
ruff check .

# Type check
mypy screencap.py
```

### Running the Tool

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

## Test Architecture

The test suite uses a two-tier approach with distinct markers:

- **Unit Tests** (`@pytest.mark.unit`): Fast, mocked function tests that run in parallel
- **Integration Tests** (`@pytest.mark.integration`): Real application testing using TextEdit with AppleScript cleanup

Integration tests create temporary files, launch TextEdit, hide windows to avoid UI interference, and properly clean up afterward.

## Key Implementation Details

### Window Filtering Logic

The tool filters out UI elements using size and title heuristics:

- Small windows (< 300x200)
- Windows with empty/system titles
- Context menu items ("New Command", "New Tab", etc.)
- Windows with newlines in titles (dropdowns)

### Configuration

- `SCREENSHOT_DIR`: Custom screenshot directory (defaults to ~/Desktop)
- `.env` file support via python-decouple
- Screenshot naming follows macOS convention: "Screenshot [App Name] YYYY-MM-DD at H.MM.SS AM/PM.png"

### Dependencies

- **python-decouple**: Environment variable management
- **sh**: Subprocess wrapper for system commands
- **pathlib**: Cross-platform path handling

### macOS Requirements

The script enforces macOS-only execution and requires:

- `getwindowid` command
- `osascript` for AppleScript
- `screencapture` utility

### Error Handling

Graceful handling of:

- Missing applications
- AppleScript failures  
- Screenshot capture errors
- Invalid window IDs

Use the fast unit test command during development for immediate feedback, and run integration tests before commits to ensure full functionality.
