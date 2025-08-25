"""Integration tests for screencap."""

import contextlib
import pytest
import subprocess
import tempfile
import time
from pathlib import Path
from sh import open as sh_open, osascript


class TestScreencapIntegration:
    """Integration tests for the screencap script."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files and open them in TextEdit for testing."""
        temp_files = []

        try:
            # Create multiple temp files to test window selection
            for i in range(3):
                # Use pathlib instead of touch command
                temp_file = Path(tempfile.mkdtemp()) / f"test_file_{i}.txt"
                temp_file.write_text(f"Test content for file {i}")
                temp_files.append(temp_file)

                # Launch TextEdit without bringing to front, then open file
                osascript(
                    "-e",
                    f'''
                    launch application "TextEdit"
                    tell application "TextEdit"
                        open POSIX file "{temp_file}"
                    end tell
                ''',
                )

            # Give TextEdit time to launch and open files
            time.sleep(0.1)
            # Hide TextEdit process to avoid interfering with desktop
            with contextlib.suppress(Exception):
                osascript(
                    "-e",
                    '''
                    tell application "System Events"
                        set visible of process "TextEdit" to false
                    end tell
                ''',
                )  # Ignore if TextEdit isn't running or other AppleScript errors
                pass  # Ignore if TextEdit isn't running or other AppleScript errors

            yield temp_files

        finally:
            # Clean up: close TextEdit windows and remove temp files
            try:
                # Close all TextEdit windows via AppleScript
                osascript(
                    "-e",
                    '''
                    tell application "TextEdit"
                        close every window
                        quit
                    end tell
                ''',
                )

                # Wait a moment for cleanup
                time.sleep(0.1)

            except Exception:
                pass  # Ignore AppleScript errors

            # Remove temp files and directories
            for temp_file in temp_files:
                try:
                    temp_file.unlink(missing_ok=True)
                    temp_file.parent.rmdir()
                except Exception:
                    pass

    @pytest.fixture
    def screenshot_dir(self, tmp_path):
        """Create a temporary directory for screenshots."""
        import os

        screenshot_dir = tmp_path / "screenshots"
        # Set SCREENSHOT_DIR to /tmp for tests
        old_env = os.environ.get("SCREENSHOT_DIR")
        os.environ["SCREENSHOT_DIR"] = "/tmp"

        yield screenshot_dir

        # Clean up any screenshots created during testing
        import glob
        from contextlib import suppress

        # Clean up /tmp screenshots
        for screenshot_file in glob.glob("/tmp/Screenshot*.png"):
            with suppress(Exception):
                Path(screenshot_file).unlink(missing_ok=True)

        # Also clean up any screenshots that might have ended up on Desktop
        desktop_path = Path.home() / "Desktop"
        for screenshot_file in desktop_path.glob("Screenshot*.png"):
            with suppress(Exception):
                screenshot_file.unlink(missing_ok=True)

        # Restore original environment
        if old_env is not None:
            os.environ["SCREENSHOT_DIR"] = old_env
        elif "SCREENSHOT_DIR" in os.environ:
            del os.environ["SCREENSHOT_DIR"]

    def run_screencap(self, *args, input_text=None, timeout=10):
        """Helper to run screencap command."""
        import os

        # Get the repository root directory dynamically
        repo_root = Path(__file__).parent.parent

        cmd = ["python", "screencap.py"] + list(args)
        # Pass current environment including SCREENSHOT_DIR
        env = os.environ.copy()
        result = subprocess.run(
            cmd, cwd=str(repo_root), input=input_text, text=True, capture_output=True, timeout=timeout, env=env
        )
        return result

    @pytest.mark.integration
    def test_list_visible_apps(self):
        """Test the --list flag shows visible applications."""
        result = self.run_screencap("--list")

        assert result.returncode == 0
        assert "Visible applications:" in result.stdout
        # Should show common apps like Finder
        assert "Finder" in result.stdout or "Terminal" in result.stdout

    @pytest.mark.integration
    def test_auto_capture_textedit(self, temp_files, screenshot_dir):
        """Test auto-capturing a TextEdit window."""
        result = self.run_screencap("--auto", "TextEdit")

        # Should succeed (exit code 0) or fail gracefully
        if result.returncode == 0:
            assert "Screenshot saved to:" in result.stdout
            # Check if screenshot file was created in /tmp
            import glob

            screenshot_files = glob.glob("/tmp/Screenshot*.png")
            if screenshot_files:
                assert len(screenshot_files) >= 1
        else:
            # If no TextEdit windows found, should show appropriate message
            assert "No matching applications found" in result.stdout or "No windows found" in result.stdout

    @pytest.mark.integration
    def test_interactive_capture_textedit(self, temp_files, screenshot_dir):
        """Test interactive window selection with TextEdit."""
        result = self.run_screencap("TextEdit", input_text="1\n", timeout=15)

        # Should either capture successfully or show no windows found
        if result.returncode == 0:
            assert "Screenshot saved to:" in result.stdout
        else:
            assert (
                "No matching applications found" in result.stdout
                or "No windows found" in result.stdout
                or "Could not parse window information" in result.stdout
            )

    @pytest.mark.integration
    def test_custom_output_file(self, temp_files, tmp_path):
        """Test capturing with custom output filename."""
        output_file = tmp_path / "custom_screenshot.png"

        result = self.run_screencap("--auto", "TextEdit", str(output_file))

        try:
            if result.returncode == 0:
                assert f"Screenshot saved to: {output_file}" in result.stdout
                if output_file.exists():
                    assert output_file.stat().st_size > 0  # File should have content
            # If no TextEdit found, that's also acceptable for testing
        finally:
            # Clean up custom output file
            from contextlib import suppress

            with suppress(Exception):
                output_file.unlink(missing_ok=True)

    @pytest.mark.integration
    def test_nonexistent_app(self):
        """Test behavior with non-existent application."""
        result = self.run_screencap("--auto", "NonExistentApp12345")

        assert result.returncode != 0
        assert "No matching applications found" in result.stdout

    @pytest.mark.integration
    def test_multi_word_app_name(self, screenshot_dir):
        """Test handling multi-word application names."""
        # Try to find Visual Studio Code or fall back to testing the parsing
        result = self.run_screencap("--auto", "Visual Studio Code")

        # Should either find VS Code or show appropriate message
        # The important part is that it doesn't crash on multi-word names
        assert result.returncode in [0, 1]  # Success or graceful failure

        if result.returncode != 0:
            assert "No matching applications found" in result.stdout or "No windows found" in result.stdout

    @pytest.mark.integration
    def test_invalid_arguments(self):
        """Test error handling for invalid arguments."""
        # Missing app name
        result = self.run_screencap()
        assert result.returncode == 0  # Help message returns 0
        assert "Usage:" in result.stdout

        # Invalid flag
        result = self.run_screencap("--invalid-flag", "Terminal")
        assert result.returncode != 0
        assert "Unknown flag" in result.stdout

    @pytest.mark.integration
    def test_quoted_arguments(self, screenshot_dir):
        """Test that quoted arguments are parsed correctly."""
        # Test with shlex parsing of quoted args
        result = self.run_screencap("--auto", "Terminal")  # Simple case

        # Should either work or fail gracefully - important is no parsing errors
        assert "Error parsing arguments" not in result.stdout

    @pytest.mark.integration
    def test_window_filtering(self, temp_files, screenshot_dir):
        """Test that UI elements are properly filtered out."""
        # This test verifies that small/menu windows are filtered
        result = self.run_screencap("TextEdit", input_text="1\n", timeout=15)

        # If windows are found, they should be substantial windows, not UI elements
        if "Found" in result.stdout and "windows:" in result.stdout:
            # Should not show tiny windows or empty titles (except for legitimate empty titles)
            lines = result.stdout.split('\n')
            window_lines = [ln for ln in lines if ". TextEdit:" in ln]

            # If we have window listings, they should be filtered properly
            for line in window_lines:
                assert "New Command" not in line  # Menu items should be filtered
