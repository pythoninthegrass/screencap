"""Unit tests for screencap functions."""

import os
import pytest
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestScreencapFunctions:
    """Unit tests for individual screencap functions."""

    @pytest.fixture(scope="session")
    def screencap_module(self):
        """Import screencap module for testing."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("screencap", Path(__file__).parent.parent / "screencap.py")
        screencap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(screencap)
        return screencap

    @pytest.mark.unit
    def test_find_matching_apps(self, screencap_module):
        """Test the find_matching_apps function."""
        apps = ["Firefox", "Terminal", "Visual Studio Code", "Finder"]

        # Test exact match
        result = screencap_module.find_matching_apps(apps, "Firefox")
        assert "Firefox" in result

        # Test partial match
        result = screencap_module.find_matching_apps(apps, "term")
        assert "Terminal" in result

        # Test case insensitive
        result = screencap_module.find_matching_apps(apps, "FIREFOX")
        assert "Firefox" in result

        # Test multi-word match
        result = screencap_module.find_matching_apps(apps, "visual")
        assert "Visual Studio Code" in result

        # Test no match
        result = screencap_module.find_matching_apps(apps, "NonExistent")
        assert len(result) == 0

    @pytest.mark.unit
    def test_get_screenshot_dir_with_env_file(self, screencap_module):
        """Test get_screenshot_dir with .env file present."""
        with patch.object(screencap_module.Path, 'cwd') as mock_cwd:
            # Mock current working directory
            mock_cwd_path = MagicMock()
            mock_cwd.return_value = mock_cwd_path

            # Mock .env file exists
            mock_env_file = MagicMock()
            mock_env_file.exists.return_value = True
            mock_cwd_path.__truediv__.return_value = mock_env_file

            # Mock the config imports
            with (
                patch('decouple.Config') as mock_config_class,
                patch('decouple.RepositoryEnv') as mock_repo_env,
                patch.object(screencap_module, 'Path') as mock_path_class,
            ):
                # Configure Path mock
                mock_expanded_path = MagicMock()
                mock_expanded_path.mkdir = MagicMock()
                mock_path_class.return_value.expanduser.return_value = mock_expanded_path

                mock_config = MagicMock()
                mock_config_class.return_value = mock_config
                mock_config.return_value = "/custom/screenshots"

                result = screencap_module.get_screenshot_dir()

                # Verify config was called
                mock_config.assert_called_once_with("SCREENSHOT_DIR", default="~/Desktop")
                mock_expanded_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

                assert result == mock_expanded_path

    @pytest.mark.unit
    def test_get_screenshot_dir_without_env_file(self, screencap_module):
        """Test get_screenshot_dir without .env file present (simplified test)."""
        # Test that the function runs without error and returns a Path object
        # when no .env file is present (this tests the default behavior)
        result = screencap_module.get_screenshot_dir()

        # Should return a Path object
        assert isinstance(result, screencap_module.Path)

        # Should be expanduser'd (no ~ in the path)
        assert "~" not in str(result)

    @pytest.mark.unit
    def test_get_screenshot_dir_default_behavior(self, screencap_module):
        """Test get_screenshot_dir with default behavior (simplified test)."""
        # Test that the function runs without error and returns a Path object
        result = screencap_module.get_screenshot_dir()

        # Should return a Path object
        assert isinstance(result, screencap_module.Path)

        # Should be expanduser'd (no ~ in the path)
        assert "~" not in str(result)

    @pytest.mark.unit
    def test_get_visible_apps_success(self, screencap_module):
        """Test get_visible_apps function with successful response."""
        with patch.object(screencap_module, 'osascript') as mock_osascript:
            mock_osascript.return_value = "Firefox, Terminal, Finder"

            result = screencap_module.get_visible_apps()

            assert "Firefox" in result
            assert "Terminal" in result
            assert "Finder" in result
            assert len(result) == 3

    @pytest.mark.unit
    def test_get_visible_apps_error(self, screencap_module):
        """Test get_visible_apps function with error."""
        with patch.object(screencap_module, 'osascript') as mock_osascript:
            mock_osascript.side_effect = Exception("AppleScript error")

            result = screencap_module.get_visible_apps()

            assert result == []

    @pytest.mark.unit
    def test_get_window_info_success(self, screencap_module):
        """Test get_window_info function with successful response."""
        mock_output = '"Test Window" size=800x600 id=12345\n"" size=0x0 id=12346'

        with patch.object(screencap_module, 'getwindowid') as mock_getwindowid, patch('builtins.print'):  # Suppress print output
            mock_getwindowid.return_value = mock_output

            result = screencap_module.get_window_info("TestApp")

            assert len(result) == 2
            assert '"Test Window" size=800x600 id=12345' in result
            assert '"" size=0x0 id=12346' in result

    @pytest.mark.unit
    def test_get_window_info_no_windows(self, screencap_module):
        """Test get_window_info function with no windows found."""
        with patch.object(screencap_module, 'getwindowid') as mock_getwindowid, patch('builtins.print'):  # Suppress print output
            # Create a custom exception that inherits from ErrorReturnCode
            from sh import ErrorReturnCode

            class MockErrorReturnCode(ErrorReturnCode):
                def __init__(self):
                    self.full_cmd = "getwindowid NonExistentApp --list"
                    self.stdout = b""
                    self.stderr = b""
                    self.exit_code = 1

            mock_getwindowid.side_effect = MockErrorReturnCode()

            result = screencap_module.get_window_info("NonExistentApp")

            assert result == []

    @pytest.mark.unit
    def test_window_parsing_regex(self):
        """Test window info parsing with regex patterns."""

        # Test cases based on actual getwindowid output
        test_cases = [
            ('"Test Window" size=800x600 id=12345', "Test Window", "12345", (800, 600)),
            ('"" size=500x500 id=23423', "", "23423", (500, 500)),
            (
                '"pythoninthegrass — -bash — 131×44" size=942x651 id=23422',
                "pythoninthegrass — -bash — 131×44",
                "23422",
                (942, 651),
            ),
        ]

        for window_info, expected_title, expected_id, expected_size in test_cases:
            # Test title extraction
            title_match = re.match(r'"([^"]*)"', window_info)
            assert title_match is not None
            assert title_match.group(1) == expected_title

            # Test ID extraction
            id_match = re.search(r'id=(\d+)', window_info)
            assert id_match is not None
            assert id_match.group(1) == expected_id

            # Test size extraction
            size_match = re.search(r'size=(\d+)x(\d+)', window_info)
            assert size_match is not None
            width, height = int(size_match.group(1)), int(size_match.group(2))
            assert (width, height) == expected_size
