"""HTTP-based MCP client for connecting to MCP servers via HTTP/SSE.

Execution Flow:
- Factory creation: create() → __init__() → connect() → establish ClientSession
- Tool discovery: get_tools() → list_tools() → convert Anthropic → OpenAI/DIAL format
- Tool execution: call_tool() → session.call_tool() → extract TextContent result
- Context management: uses async context managers for streams and session lifecycle
- Error handling: raises RuntimeError if session not initialized before operations

External I/O:
- HTTP/SSE connection to remote MCP server (streamablehttp_client)
- Async read/write streams for bidirectional communication
"""

import logging
from typing import Optional, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent

logger = logging.getLogger(__name__)


class HttpMCPClient:
    """Handles MCP server connection and tool execution.
    
    Manages async connection lifecycle to HTTP-based MCP servers using SSE transport.
    Provides tool discovery and execution with format conversion between MCP (Anthropic)
    and DIAL/OpenAI specifications.
    """

    def __init__(self, mcp_server_url: str) -> None:
        """Initialize MCP client instance (does not connect yet).
        
        Args:
            mcp_server_url: Full HTTP URL to the MCP server endpoint (e.g., "http://localhost:8005/mcp")
            
        Note:
            Connection is deferred to connect() method. Use create() factory for
            immediate connection establishment.
        """
        self.server_url = mcp_server_url
        self.session: Optional[ClientSession] = None  # Set after connect()
        self._streams_context = None  # Async context manager for HTTP streams
        self._session_context = None  # Async context manager for ClientSession
        logger.debug("HttpMCPClient instance created", extra={"server_url": mcp_server_url})

    @classmethod
    async def create(cls, mcp_server_url: str) -> 'HttpMCPClient':
        """Async factory method to create and connect MCPClient.
        
        Args:
            mcp_server_url: Full HTTP URL to the MCP server endpoint
            
        Returns:
            HttpMCPClient: Fully connected and initialized client instance
            
        Raises:
            Network errors from underlying HTTP/SSE connection
            
        Note:
            Preferred over __init__() + connect() as it ensures client is ready for use.
        """
        instance = cls(mcp_server_url)
        await instance.connect()  # Blocks until connection established
        return instance

    async def connect(self):
        """Establish HTTP/SSE connection to MCP server and initialize session.
        
        Connection flow:
        1. Create HTTP streaming context (SSE transport)
        2. Enter context to get bidirectional read/write streams
        3. Create ClientSession with streams
        4. Initialize MCP protocol handshake
        
        Side effects:
            - Sets self.session to active ClientSession
            - Stores context managers for cleanup on disconnect
            
        Raises:
            Connection errors if server unreachable or handshake fails
        """
        # Create HTTP/SSE transport layer
        self._streams_context = streamablehttp_client(self.server_url)
        # Enter context to establish connection and get streams
        read_stream, write_stream, _ = await self._streams_context.__aenter__()
        
        # Wrap streams in MCP ClientSession
        self._session_context = ClientSession(read_stream, write_stream)
        self.session = await self._session_context.__aenter__()
        
        # Complete MCP protocol handshake and get server capabilities
        init_result = await self.session.initialize()
        logger.info(f"Connected to MCP server: {self.server_url}, capabilities: {init_result}")

    async def get_tools(self) -> list[dict[str, Any]]:
        """Retrieve available tools from MCP server and convert to DIAL/OpenAI format.
        
        Returns:
            List of tool definitions in DIAL format:
            [
                {
                    "type": "function",
                    "function": {
                        "name": "tool_name",
                        "description": "tool description",
                        "parameters": {JSON schema}
                    }
                }
            ]
            
        Raises:
            RuntimeError: If session not initialized (must call connect() first)
            
        Note:
            MCP uses Anthropic format {name, description, inputSchema}.
            DIAL/OpenAI uses {type: "function", function: {name, description, parameters}}.
        """
        # Precondition: session must be active
        if not self.session:
            raise RuntimeError("MCP client is not connected to MCP server")
        
        # Fetch tools from MCP server (network call)
        tools_result = await self.session.list_tools()
        
        # Convert from MCP (Anthropic) format to DIAL (OpenAI) format
        dial_tools = []
        for tool in tools_result.tools:
            dial_tool = {
                "type": "function",  # Required by OpenAI spec
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema  # inputSchema → parameters
                }
            }
            dial_tools.append(dial_tool)
        
        logger.info(f"Retrieved {len(dial_tools)} tools from {self.server_url}: {[t['function']['name'] for t in dial_tools]}")
        return dial_tools

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Execute a specific tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to execute (must exist on server)
            tool_args: Dictionary of arguments matching tool's inputSchema
            
        Returns:
            - str: Extracted text if result contains TextContent
            - list[Content]: Raw content array for other content types
            
        Raises:
            RuntimeError: If session not initialized (must call connect() first)
            Tool execution errors from MCP server
            
        Note:
            MCP tools can return multiple content items (text, images, resources).
            This implementation extracts text from the first TextContent item for
            simplicity. Other content types return raw content array.
        """
        # Precondition: session must be active
        if not self.session:
            raise RuntimeError("MCP client is not connected to MCP server")
        
        logger.info(f"Calling tool '{tool_name}' on {self.server_url} with args: {tool_args}")
        
        # Execute tool on MCP server (network call, may be slow)
        result = await self.session.call_tool(tool_name, tool_args)
        content = result.content
        
        # Extract text from first content item if it's TextContent
        # (Most common case for UMS/Fetch tools)
        if content and len(content) > 0:
            first_element = content[0]
            if isinstance(first_element, TextContent):
                return first_element.text  # Return plain string
        
        # Fallback: return raw content for non-text or empty results
        return content
