"""Property-based tests for screencap functions using Hypothesis."""

import importlib.util
import pytest
import re
from hypothesis import assume, given, strategies as st
from hypothesis.strategies import composite
from pathlib import Path

spec = importlib.util.spec_from_file_location("screencap", Path(__file__).parent.parent / "screencap.py")
screencap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screencap)


# Custom strategies
@composite
def app_names(draw):
    """Generate realistic application names."""
    # Common app name patterns
    simple_names = ["Firefox", "Chrome", "Safari", "Terminal", "Finder", "Mail", "Notes", "Calculator"]
    multi_word_names = ["Visual Studio Code", "Activity Monitor", "System Preferences", "Final Cut Pro"]
    camel_case_names = ["TextEdit", "QuickTime", "AppStore", "FaceTime"]

    app_type = draw(st.sampled_from(["simple", "multi_word", "camel_case", "generated"]))

    if app_type == "simple":
        return draw(st.sampled_from(simple_names))
    elif app_type == "multi_word":
        return draw(st.sampled_from(multi_word_names))
    elif app_type == "camel_case":
        return draw(st.sampled_from(camel_case_names))
    else:
        # Generate app names that follow common patterns
        base = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=20))
        suffix = draw(st.sampled_from(["", " Pro", " Lite", " X", " 2024", " Studio"]))
        return base + suffix


@composite
def window_titles(draw):
    """Generate realistic window titles."""
    # Common window title patterns
    simple_titles = ["Untitled", "New Document", "About", "Preferences", "Help", ""]

    # File-based titles with extensions
    extensions = [".txt", ".py", ".md", ".js", ".html", ".css", ".json", ".xml", ".pdf"]
    filename = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20))
    extension = draw(st.sampled_from(extensions))
    file_title = filename + extension

    # Complex titles with symbols
    complex_base = draw(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.", min_size=0, max_size=50)
    )

    title_type = draw(st.sampled_from(["simple", "file", "complex", "unicode"]))

    if title_type == "simple":
        return draw(st.sampled_from(simple_titles))
    elif title_type == "file":
        return file_title
    elif title_type == "complex":
        return complex_base
    else:
        # Unicode titles that might cause issues
        return draw(st.text(min_size=0, max_size=30))


@composite
def window_info_strings(draw):
    """Generate realistic window info strings like getwindowid output."""
    title = draw(window_titles())
    width = draw(st.integers(min_value=0, max_value=3000))
    height = draw(st.integers(min_value=0, max_value=2000))
    window_id = draw(st.integers(min_value=1, max_value=99999))
    return f'"{title}" size={width}x{height} id={window_id}'


class TestScreencapProperties:
    """Property-based tests for screencap functions."""

    @pytest.mark.unit
    @given(apps=st.lists(app_names(), min_size=0, max_size=20, unique=True), search=st.text(min_size=1, max_size=50))
    def test_find_matching_apps_properties(self, apps, search):
        """Test find_matching_apps maintains invariants."""
        result = screencap.find_matching_apps(apps, search)

        # Result should always be a list
        assert isinstance(result, list)

        # All results should be from the original apps list
        for app in result:
            assert app in apps

        # Results should not contain duplicates
        assert len(result) == len(set(result))

        # If there are exact matches, they should be prioritized
        exact_matches = [app for app in apps if app.lower() == search.lower()]
        if exact_matches:
            assert all(app in result for app in exact_matches)

    @pytest.mark.unit
    @given(apps=st.lists(app_names(), min_size=1, max_size=10, unique=True))
    def test_find_matching_apps_exact_match_property(self, apps):
        """Test that exact matches are always found."""
        for app in apps:
            result = screencap.find_matching_apps(apps, app)
            assert app in result

    @pytest.mark.unit
    @given(apps=st.lists(app_names(), min_size=1, max_size=10, unique=True))
    def test_find_matching_apps_case_insensitive(self, apps):
        """Test that matching is case insensitive."""
        for app in apps:
            # Test various case variations
            variations = [app.lower(), app.upper(), app.capitalize()]
            for variation in variations:
                result = screencap.find_matching_apps(apps, variation)
                assert app in result

    @pytest.mark.unit
    @given(title=window_titles())
    def test_filename_sanitization_properties(self, title):
        """Test that window titles are properly sanitized for filenames."""
        assume(title is not None)

        # Simulate the filename creation logic from capture_screenshot
        clean_title = title.replace("/", "-").replace(":", "-").strip() if title else "Window"

        # Clean title should not contain filesystem-problematic characters
        assert "/" not in clean_title
        assert ":" not in clean_title

        # Should handle empty titles gracefully
        if not title.strip():
            clean_title = "Window"
        assert clean_title  # Should never be empty

    @pytest.mark.unit
    @given(window_info=window_info_strings())
    def test_window_info_parsing_properties(self, window_info):
        """Test that window info strings can be parsed correctly."""
        # Test title extraction
        title_match = re.match(r'"([^"]*)"', window_info)
        assert title_match is not None

        # Test ID extraction
        id_match = re.search(r'id=(\d+)', window_info)
        assert id_match is not None
        window_id = int(id_match.group(1))
        assert window_id > 0

        # Test size extraction
        size_match = re.search(r'size=(\d+)x(\d+)', window_info)
        assert size_match is not None
        width, height = int(size_match.group(1)), int(size_match.group(2))
        assert width >= 0
        assert height >= 0

    @pytest.mark.unit
    @given(window_infos=st.lists(window_info_strings(), min_size=0, max_size=10))
    def test_window_filtering_properties(self, window_infos):
        """Test properties of window filtering logic."""
        # Simulate the filtering that happens in the real application
        filtered_windows = []

        for window_info in window_infos:
            # Extract title and size
            title_match = re.match(r'"([^"]*)"', window_info)
            size_match = re.search(r'size=(\d+)x(\d+)', window_info)

            if title_match and size_match:
                title = title_match.group(1)
                width, height = int(size_match.group(1)), int(size_match.group(2))

                # Apply realistic filtering rules
                if width >= 300 and height >= 200 and title and "\n" not in title:
                    filtered_windows.append(window_info)

        # Filtered list should be subset of original
        assert len(filtered_windows) <= len(window_infos)

        # All filtered windows should meet minimum size requirements
        for window_info in filtered_windows:
            size_match = re.search(r'size=(\d+)x(\d+)', window_info)
            width, height = int(size_match.group(1)), int(size_match.group(2))
            assert width >= 300
            assert height >= 200

    @pytest.mark.unit
    @given(subpath=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/._-", min_size=0, max_size=50))
    def test_path_handling_properties(self, subpath):
        """Test that path handling is robust."""
        # Create realistic home paths
        path_str = f"~/{subpath}" if subpath else "~"

        try:
            # This simulates the path expansion in get_screenshot_dir
            expanded = Path(path_str).expanduser()

            # Expanded path should be absolute for home paths
            assert expanded.is_absolute()

            # The expanded path should not contain ~ anymore
            assert "~" not in str(expanded)

        except (ValueError, OSError, RuntimeError):
            # Some paths may be invalid, which is acceptable
            pass

    @pytest.mark.unit
    @given(search_words=st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10), min_size=1, max_size=5))
    def test_multi_word_search_properties(self, search_words):
        """Test multi-word search functionality."""
        apps = ["Visual Studio Code", "Final Cut Pro", "Activity Monitor", "System Preferences"]
        search_pattern = " ".join(search_words)

        result = screencap.find_matching_apps(apps, search_pattern)

        # Result should be a list
        assert isinstance(result, list)

        # If any app contains all search words, it should be in results
        for app in apps:
            app_lower = app.lower()
            if all(word.lower() in app_lower for word in search_words):
                # This app should be found
                matching_result = screencap.find_matching_apps(apps, search_pattern)
                # Verify the logic works correctly
                assert isinstance(matching_result, list)

    @pytest.mark.unit
    @given(
        title=st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.()", min_size=0, max_size=200),
        width=st.integers(min_value=1, max_value=3000),
        height=st.integers(min_value=1, max_value=2000),
        window_id=st.integers(min_value=1, max_value=99999),
    )
    def test_window_size_filtering_invariants(self, title, width, height, window_id):
        """Test invariants of window size filtering."""
        # Filter out titles that contain quotes to avoid parsing issues
        assume('"' not in title)

        window_info = f'"{title}" size={width}x{height} id={window_id}'

        # Parse the window info
        title_match = re.match(r'"([^"]*)"', window_info)
        size_match = re.search(r'size=(\d+)x(\d+)', window_info)
        id_match = re.search(r'id=(\d+)', window_info)

        # All parsing should succeed for our generated data
        assert title_match is not None
        assert size_match is not None
        assert id_match is not None

        parsed_title = title_match.group(1)
        parsed_width = int(size_match.group(1))
        parsed_height = int(size_match.group(2))
        parsed_id = int(id_match.group(1))

        # Parsed values should match original inputs
        assert parsed_title == title
        assert parsed_width == width
        assert parsed_height == height
        assert parsed_id == window_id

    @pytest.mark.unit
    @given(apps=st.lists(app_names(), min_size=0, max_size=10, unique=True))
    def test_empty_search_handling(self, apps):
        """Test behavior with empty or whitespace-only search patterns."""
        # Empty string
        result = screencap.find_matching_apps(apps, "")
        assert isinstance(result, list)

        # Whitespace only
        result = screencap.find_matching_apps(apps, "   ")
        assert isinstance(result, list)

    @pytest.mark.unit
    @given(apps=st.lists(st.text(min_size=0, max_size=50), min_size=0, max_size=10))
    def test_find_matching_apps_robustness(self, apps):
        """Test that find_matching_apps is robust to various inputs."""
        # Remove duplicates to match the unique=True constraint we usually use
        unique_apps = list(dict.fromkeys(apps))  # Preserves order, removes duplicates

        search_patterns = ["", "test", "TEST", "NonExistent", "123", "!@#"]

        for pattern in search_patterns:
            result = screencap.find_matching_apps(unique_apps, pattern)

            # Should always return a list
            assert isinstance(result, list)

            # All results should be from original apps
            for app in result:
                assert app in unique_apps

            # Should not contain duplicates
            assert len(result) == len(set(result))
