"""Stdio-based MCP Client for Docker-hosted MCP servers.

Execution Flow:
1. Create instance via async factory (create()) - prevents blocking constructor
2. Connect establishes nested async contexts: stdio transport → session → initialize
3. Format conversion: MCP (Anthropic) tools → DIAL (OpenAI) function calling schema
4. Tool execution returns structured results, extracting TextContent when available

Key Design Decisions:
- Async factory pattern required because __init__ can't be async
- Two-level context managers ensure proper cleanup of stdio streams and session
- Docker stdio provides isolation and consistent environment for MCP servers
"""

import logging
from typing import Optional, Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

logger = logging.getLogger(__name__)


class StdioMCPClient:
    """Manages MCP server connections via Docker stdio transport.
    
    This client communicates with MCP servers running in Docker containers,
    using stdin/stdout for transport. Requires Docker to be installed and running.
    """

    def __init__(self, docker_image: str) -> None:
        """Initialize client (private - use create() factory method instead).
        
        Args:
            docker_image: Docker image name (e.g., 'mcp/duckduckgo:latest')
            
        Note:
            Direct instantiation leaves client unconnected. Always use the
            async factory method create() which handles connection setup.
        """
        self.docker_image = docker_image
        self.session: Optional[ClientSession] = None  # Active MCP session, set after connect()
        self._stdio_context = None  # Async context for Docker stdio streams
        self._session_context = None  # Async context for MCP session lifecycle
        logger.debug("StdioMCPClient instance created", extra={"docker_image": docker_image})

    @classmethod
    async def create(cls, docker_image: str) -> 'StdioMCPClient':
        """Async factory method to create and connect MCP client (REQUIRED).
        
        Args:
            docker_image: Docker image name containing the MCP server
            
        Returns:
            Fully connected StdioMCPClient instance ready for tool operations
            
        Raises:
            RuntimeError: If Docker is unavailable or image cannot be pulled
            
        Example:
            client = await StdioMCPClient.create('mcp/duckduckgo:latest')
            tools = await client.get_tools()
        """
        instance = cls(docker_image)
        await instance.connect()  # Establish connection before returning
        return instance

    async def connect(self):
        """Establish connection to MCP server via Docker stdio.
        
        Creates two nested async context managers:
        1. stdio_client: Manages Docker process and stdin/stdout streams
        2. ClientSession: Handles MCP protocol handshake and message exchange
        
        The --rm flag ensures containers are cleaned up after disconnection.
        The -i flag keeps stdin open for bidirectional communication.
        
        Raises:
            RuntimeError: If Docker command fails or MCP initialization fails
        """
        # Configure Docker to run MCP server with stdio transport
        server_params = StdioServerParameters(
            command="docker",
            args=["run", "--rm", "-i", self.docker_image]  # --rm auto-cleans container
        )
        
        # Enter stdio context to get read/write streams
        self._stdio_context = stdio_client(server_params)
        read_stream, write_stream, _ = await self._stdio_context.__aenter__()
        
        # Enter session context for MCP protocol communication
        self._session_context = ClientSession(read_stream, write_stream)
        self.session = await self._session_context.__aenter__()
        
        # Complete MCP handshake - server announces capabilities
        init_result = await self.session.initialize()
        logger.info(f"Connected to MCP server via Docker: {self.docker_image}, capabilities: {init_result}")

    async def get_tools(self) -> list[dict[str, Any]]:
        """Retrieve available tools and convert to DIAL/OpenAI format.
        
        Returns:
            List of tool definitions in DIAL (OpenAI) function calling format:
            [{
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "what it does",
                    "parameters": {JSON schema}
                }
            }]
            
        Raises:
            RuntimeError: If client is not connected (call create() first)
            
        Note:
            MCP servers return Anthropic format (inputSchema), but DIAL expects
            OpenAI format (parameters). This method handles the conversion.
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected to MCP server")
        
        # Fetch tools from MCP server (returns Anthropic format)
        tools_result = await self.session.list_tools()
        
        # Convert from MCP (Anthropic) format to DIAL (OpenAI) format
        # MCP: {name, description, inputSchema}
        # DIAL: {type: "function", function: {name, description, parameters}}
        dial_tools = []
        for tool in tools_result.tools:
            dial_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema  # inputSchema → parameters
                }
            }
            dial_tools.append(dial_tool)
        
        logger.info(f"Retrieved {len(dial_tools)} tools from {self.docker_image}: {[t['function']['name'] for t in dial_tools]}")
        return dial_tools

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Execute a tool on the MCP server with provided arguments.
        
        Args:
            tool_name: Name of the tool to call (from get_tools() list)
            tool_args: Dictionary of arguments matching the tool's parameter schema
            
        Returns:
            - String: If result contains TextContent (most common case)
            - Raw content list: For non-text results (images, structured data)
            
        Raises:
            RuntimeError: If client is not connected
            
        Note:
            MCP returns results as a list of content items. We extract the first
            TextContent.text for simplicity, as most tools return plain text.
            For complex multi-content responses, raw content list is returned.
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected to MCP server")
        
        logger.info(f"Calling tool '{tool_name}' on {self.docker_image} with args: {tool_args}")
        
        # Execute tool via MCP protocol
        result = await self.session.call_tool(tool_name, tool_args)
        content = result.content
        
        # Extract text from first content item if available (common case)
        # MCP can return multiple content items (text, images, etc.)
        if content and len(content) > 0:
            first_element = content[0]
            if isinstance(first_element, TextContent):
                return first_element.text  # Return plain text for simplicity
        
        # Fall back to raw content for non-text or empty results
        return content
