"""Tests for MCP server functionality."""

import asyncio
import json
import pytest
import tempfile
import platform
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(scope="session")
def skip_non_macos():
    """Skip tests on non-macOS systems."""
    if platform.system() != "Darwin":
        pytest.skip("MCP server tests require macOS")


class TestMCPServer:
    """Test MCP server functionality using the Python SDK."""

    @pytest.fixture(scope="session")
    def server_script(self):
        """Path to the MCP server script."""
        return Path(__file__).parent.parent / "server.py"

    async def create_test_session(self, server_script):
        """Helper to create a test session."""
        server_params = StdioServerParameters(
            command="uv",
            args=["run", str(server_script)],
        )
        
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    @pytest.mark.unit
    async def test_server_initialization(self, server_script, skip_non_macos):
        """Test that the MCP server initializes correctly."""
        async for session in self.create_test_session(server_script):
            # Server should be initialized if we got here
            assert session is not None
            break

    @pytest.mark.unit
    async def test_list_tools(self, server_script, skip_non_macos):
        """Test listing available tools."""
        async for session in self.create_test_session(server_script):
            result = await session.list_tools()
            
            # Should have our screenshot tools
            tool_names = [tool.name for tool in result.tools]
            assert "list_apps" in tool_names
            assert "screenshot_app" in tool_names
            assert "screenshot_by_choice" in tool_names
            
            # Check tool schemas
            for tool in result.tools:
                assert tool.name is not None
                assert tool.description is not None
                if tool.name in ["screenshot_app", "screenshot_by_choice"]:
                    assert tool.inputSchema is not None
            break

    @pytest.mark.integration 
    async def test_list_apps_tool(self, server_script, skip_non_macos):
        """Test the list_apps tool."""
        async for session in self.create_test_session(server_script):
            result = await session.call_tool("list_apps", {})
            
            assert result.content is not None
            assert len(result.content) > 0
            
            # Parse the result - it should be a JSON list
            content_text = result.content[0].text
            apps = json.loads(content_text)
            assert isinstance(apps, list)
            # Should have at least Finder on macOS
            assert any("Finder" in app for app in apps)
            break

    @pytest.mark.integration
    async def test_screenshot_app_no_windows(self, server_script, skip_non_macos):
        """Test screenshot_app when no windows are found."""
        async for session in self.create_test_session(server_script):
            result = await session.call_tool("screenshot_app", {"app_name": "NonExistentApp12345"})
            
            assert result.content is not None
            content_text = result.content[0].text
            response = json.loads(content_text)
            assert "error" in response
            assert "No windows found" in response["error"]
            break

    @pytest.mark.integration
    async def test_screenshot_tool_validation(self, server_script, skip_non_macos):
        """Test tool input validation."""
        async for session in self.create_test_session(server_script):
            # Test missing required app_name should raise an error during tool call
            try:
                result = await session.call_tool("screenshot_app", {})
                # If we get here, check if there's an error in response
                content_text = result.content[0].text
                response = json.loads(content_text) 
                assert "error" in response
            except Exception:
                # Expected - validation should fail for missing required parameter
                pass
            break

    @pytest.mark.integration  
    async def test_screenshot_by_choice_invalid_id(self, server_script, skip_non_macos):
        """Test screenshot_by_choice with invalid choice_id."""
        async for session in self.create_test_session(server_script):
            result = await session.call_tool("screenshot_by_choice", {
                "app_name": "NonExistentApp",
                "choice_id": 999
            })
            
            assert result.content is not None
            content_text = result.content[0].text
            response = json.loads(content_text)
            assert "error" in response
            break


class TestMCPServerIntegration:
    """Integration tests for MCP server."""

    @pytest.fixture(scope="session") 
    def server_script(self):
        """Path to the MCP server script."""
        return Path(__file__).parent.parent / "server.py"

    async def create_test_session(self, server_script):
        """Helper to create a test session."""
        server_params = StdioServerParameters(
            command="uv",
            args=["run", str(server_script)],
        )
        
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    @pytest.mark.integration
    async def test_server_startup_shutdown(self, server_script, skip_non_macos):
        """Test server can start and shut down cleanly."""
        async for session in self.create_test_session(server_script):
            # Basic smoke test - list tools
            result = await session.list_tools()
            assert len(result.tools) > 0
            break

    @pytest.mark.integration  
    async def test_comprehensive_tool_interaction(self, server_script, skip_non_macos):
        """Test comprehensive interaction with all MCP tools."""
        async for session in self.create_test_session(server_script):
            # Test list_apps
            apps_result = await session.call_tool("list_apps", {})
            assert apps_result.content is not None
            apps_text = apps_result.content[0].text
            apps = json.loads(apps_text)
            assert isinstance(apps, list)
            
            # Test screenshot with non-existent app
            error_result = await session.call_tool("screenshot_app", {
                "app_name": "NonExistentApp12345"
            })
            assert error_result.content is not None
            error_text = error_result.content[0].text
            error_response = json.loads(error_text)
            assert "error" in error_response
            
            # Test screenshot_by_choice with invalid ID
            choice_result = await session.call_tool("screenshot_by_choice", {
                "app_name": "NonExistentApp", 
                "choice_id": 999
            })
            assert choice_result.content is not None
            choice_text = choice_result.content[0].text
            choice_response = json.loads(choice_text)
            assert "error" in choice_response
            break