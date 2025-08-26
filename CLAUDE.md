# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**screencap** is a macOS-specific command-line tool for capturing screenshots of application windows. It uses native macOS utilities (AppleScript, screencapture) along with getwindowid to intelligently find and screenshot application windows with smart filtering of UI elements. The project also includes an MCP (Model Context Protocol) server for AI integration.

## Architecture

- **Self-Contained Script**: Uses uv's inline script format with dependencies embedded in `screencap.py`
- **Native Integration**: Leverages macOS system commands via the `sh` library for subprocess management
- **Smart Discovery**: Pattern-based app matching with sophisticated window filtering to exclude menus/dialogs
- **Configurable Output**: Supports custom screenshot directories via `SCREENSHOT_DIR` environment variable
- **MCP Server**: FastMCP server (`server.py`) exposing screenshot functionality via Model Context Protocol

## Development Commands

### Testing (Four-Tier Strategy)

```bash
# Fast unit/property tests with parallel execution (1.04s, 22 tests)
uv run pytest -v -m unit -n auto

# Integration tests (sequential, 13.22s, 15 tests) 
uv run pytest -v -m integration

# All tests (37 total, ~18s)
uv run pytest -v

# MCP-specific tests (8 tests)
uv run pytest tests/test_mcp.py -v

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

### MCP Server

```bash
# Run MCP server directly
uv run server.py

# Run MCP server in development mode (with auto-restart)
uv run mcp dev server.py

# Install MCP server for Claude Desktop
uv run mcp install server.py --name "Screencap Server"
```

## Test Architecture

The test suite uses a four-tier approach with distinct markers:

- **Unit Tests** (`@pytest.mark.unit`): Fast, mocked function tests that run in parallel (20 tests)
- **Property-Based Tests** (`@pytest.mark.unit` with Hypothesis): Automated edge case testing using random data generation (11 tests) 
- **Integration Tests** (`@pytest.mark.integration`): Real application testing using TextEdit with AppleScript cleanup (15 tests)
- **MCP Tests** (`tests/test_mcp.py`): Model Context Protocol server testing using official MCP Python SDK (8 tests)

### Test Types

**Core Functionality Tests**: Integration tests create temporary files, launch TextEdit, hide windows to avoid UI interference, and properly clean up afterward. Property-based tests use Hypothesis to generate thousands of test cases automatically, covering edge cases that manual testing might miss.

**MCP Server Tests**: Comprehensive testing of FastMCP server implementation including:
- Server initialization and tool discovery
- Real MCP client-server communication via STDIO transport  
- Tool validation (`list_apps`, `screenshot_app`, `screenshot_by_choice`)
- Error handling and input validation
- JSON response parsing and schema validation

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

**Core Dependencies**:
- **python-decouple**: Environment variable management
- **sh**: Subprocess wrapper for system commands
- **pathlib**: Cross-platform path handling

**MCP Server Dependencies**:
- **FastMCP**: High-level MCP server framework
- **httpx**: HTTP client for MCP communication (pinned to stable version)
- **httpx-sse**: Server-sent events support
- **pydantic**: Data validation (pinned for compatibility)

### macOS Requirements

Both the CLI tool and MCP server enforce macOS-only execution and require:

- `getwindowid` command
- `osascript` for AppleScript
- `screencapture` utility

### Error Handling

Graceful handling of:

- Missing applications
- AppleScript failures  
- Screenshot capture errors
- Invalid window IDs
- MCP protocol errors and validation failures
- Signal handling (SIGINT, SIGTERM) with graceful shutdown

### MCP Server Features

The FastMCP server (`server.py`) provides three main tools:

1. **`list_apps`**: Returns a JSON array of visible macOS applications
2. **`screenshot_app`**: Captures screenshots with options for auto-selection and custom output paths
3. **`screenshot_by_choice`**: Allows selection from multiple windows when ambiguous matches exist

**Signal Handling**: The server handles SIGINT (Ctrl+C) gracefully with a 2-second timeout, and SIGTERM for clean shutdowns. Multiple SIGINT signals force immediate exit.

**Development**: Use `uv run pytest tests/test_mcp.py -v` to test MCP functionality, and the general test commands for overall project health. MCP tests require macOS and are automatically skipped on other platforms.
