"""
DIAL API client with MCP tool integration.
Orchestrates LLM interactions, recursive tool calling, and streaming responses.
"""

import json
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator

from openai import AsyncAzureOpenAI

from agent.clients.stdio_mcp_client import StdioMCPClient
from agent.models.message import Message, Role
from agent.clients.http_mcp_client import HttpMCPClient

logger = logging.getLogger(__name__)


class DialClient:
    """
    DIAL API wrapper with recursive tool calling loop.
    
    Responsibilities:
    - Connect to DIAL API (Azure OpenAI-compatible endpoint)
    - Convert messages to/from OpenAI format
    - Execute tool calls via MCP clients (HTTP or stdio)
    - Handle recursive tool calling until completion
    - Support both streaming and non-streaming responses
    """

    def __init__(
            self,
            api_key: str,
            endpoint: str,
            model: str,
            tools: list[dict[str, Any]],
            tool_name_client_map: dict[str, HttpMCPClient | StdioMCPClient]
    ):
        """
        Initialize DIAL client with credentials and MCP integrations.
        
        Args:
            api_key: DIAL API authentication key
            endpoint: DIAL API base URL (e.g., https://ai-proxy.lab.epam.com)
            model: Model identifier (e.g., "gpt-4o", "claude-3-7-sonnet@20250219")
            tools: List of tools in OpenAI/DIAL format (type="function")
            tool_name_client_map: Maps tool names to their MCP client executors
        
        Note: api_version="" is required for DIAL compatibility (not standard Azure OpenAI)
        """
        self.tools = tools
        self.tool_name_client_map = tool_name_client_map
        self.model = model
        # DIAL requires empty api_version string (differs from Azure OpenAI)
        self.async_openai = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=""  # DIAL-specific: must be empty string
        )

    async def response(self, messages: list[Message]) -> Message:
        """
        Execute non-streaming completion with recursive tool calling.
        
        Args:
            messages: Conversation history (system, user, assistant, tool messages)
        
        Returns:
            Final assistant message (after all tool calls complete)
        
        Flow:
            1. Call LLM with current messages
            2. If response contains tool_calls, execute them via MCP clients
            3. Append tool results and recursively call LLM again
            4. Repeat until LLM returns without tool_calls
        
        Note: Modifies messages list in-place by appending assistant/tool messages
        """
        # Call LLM with messages and available tools
        response = await self.async_openai.chat.completions.create(
            model=self.model,
            messages=[msg.to_dict() for msg in messages],
            tools=self.tools if self.tools else None  # Only pass tools if available
        )
        
        # Convert OpenAI response to our Message model
        ai_message = Message(
            role=Role.ASSISTANT,
            content=response.choices[0].message.content
        )
        
        # Extract tool calls if present (LLM wants to use tools)
        if response.choices[0].message.tool_calls:
            ai_message.tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in response.choices[0].message.tool_calls
            ]
        
        # Recursive tool calling loop
        if ai_message.tool_calls:
            messages.append(ai_message)  # Add assistant message with tool calls
            await self._call_tools(ai_message, messages)  # Execute tools, append results
            return await self.response(messages)  # Recurse: let LLM process tool results
        
        # Base case: no tool calls, return final answer
        return ai_message

    async def stream_response(self, messages: list[Message]) -> AsyncGenerator[str, None]:
        """
        Streaming completion with tool calling support.
        Yields SSE-formatted chunks.
        """
        # 1. Create streaming chat completions request
        stream = await self.async_openai.chat.completions.create(
            model=self.model,
            messages=[msg.to_dict() for msg in messages],
            tools=self.tools if self.tools else None,
            stream=True
        )
        
        # 2. Create empty string to collect content while streaming
        content_buffer = ""
        
        # 3. Create empty array for tool call deltas
        tool_deltas = []
        
        # 4. Make async loop through stream
        async for chunk in stream:
            # Get delta chunk
            delta = chunk.choices[0].delta
            
            # If delta contains content
            if delta.content:
                # Create chunk data
                chunk_data = {
                    "choices": [{
                        "delta": {"content": delta.content},
                        "index": 0,
                        "finish_reason": None
                    }]
                }
                # Yield SSE-formatted chunk
                yield f"data: {json.dumps(chunk_data)}\n\n"
                # Concat content_buffer with delta content
                content_buffer += delta.content
            
            # If delta has tool calls then extend tool_deltas
            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)
        
        # 5. If tool_deltas are present
        if tool_deltas:
            # Collect tool calls with _collect_tool_calls method
            tool_calls = self._collect_tool_calls(tool_deltas)
            # Create assistant message with collected content and tool calls
            ai_message = Message(
                role=Role.ASSISTANT,
                content=content_buffer,
                tool_calls=tool_calls
            )
            # Add created assistant message to messages
            messages.append(ai_message)
            # Call _call_tools (it's async, don't forget about await)
            await self._call_tools(ai_message, messages)
            # Make recursive call with messages to process further
            async for chunk in self.stream_response(messages):
                yield chunk
            return
        
        # 6. Add assistant message with collected content
        messages.append(Message(role=Role.ASSISTANT, content=content_buffer))
        
        # 7. Create final chunk dict
        final_chunk = {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}
        
        # 8. Yield final chunk
        yield f"data: {json.dumps(final_chunk)}\n\n"
        
        # 9. Yield [DONE]
        yield "data: [DONE]\n\n"

    def _collect_tool_calls(self, tool_deltas):
        """
        Reassemble streaming tool call deltas into complete tool call objects.
        
        Args:
            tool_deltas: List of partial tool call chunks from streaming response
        
        Returns:
            List of complete tool call dicts with id, type, and function (name + arguments)
        
        Note: Each delta contains an index for multi-tool scenarios. Arguments arrive
              incrementally and must be concatenated (like streaming content).
        """
        # Group deltas by index (handles multiple simultaneous tool calls)
        tool_dict = defaultdict(lambda: {
            "id": None,
            "function": {"arguments": "", "name": None},
            "type": None
        })
        
        # Merge deltas: IDs/names arrive once, arguments stream incrementally
        for delta in tool_deltas:
            idx = delta.index
            if delta.id:
                tool_dict[idx]["id"] = delta.id
            if delta.function and delta.function.name:
                tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function and delta.function.arguments:
                # Accumulate arguments (streamed in chunks, must concatenate)
                tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type:
                tool_dict[idx]["type"] = delta.type
        
        return list(tool_dict.values())

    async def _call_tools(self, ai_message: Message, messages: list[Message], silent: bool = False):
        """
        Execute all tool calls in assistant message via MCP clients.
        
        Args:
            ai_message: Assistant message containing tool_calls array
            messages: Conversation history (tool results appended here)
            silent: Unused parameter (reserved for future logging control)
        
        Side effects:
            - Appends tool result messages to `messages` list
            - Logs errors for failed tool executions
        
        Error handling:
            - Unknown tools: Returns error message, continues to next tool
            - Execution failures: Catches all exceptions, returns error to LLM
        """
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["function"]["name"]
            # Parse JSON arguments (LLM returns them as string)
            tool_args = json.loads(tool_call["function"]["arguments"])
            
            # Resolve tool name to MCP client (HTTP or stdio)
            mcp_client = self.tool_name_client_map.get(tool_name)
            
            # Handle unknown tool (shouldn't happen if tools list is synced)
            if not mcp_client:
                tool_message = Message(
                    role=Role.TOOL,
                    content=f"Error: Tool '{tool_name}' not found",
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
                messages.append(tool_message)
                continue
            
            # Execute tool via MCP client
            try:
                result = await mcp_client.call_tool(tool_name, tool_args)
                tool_message = Message(
                    role=Role.TOOL,
                    content=str(result),  # Convert result to string for LLM
                    tool_call_id=tool_call["id"],  # Required for OpenAI format
                    name=tool_name
                )
                messages.append(tool_message)
            except Exception as e:
                # Log error but continue (let LLM handle error message)
                logger.error(f"Error calling tool {tool_name}: {e}")
                tool_message = Message(
                    role=Role.TOOL,
                    content=f"Error executing tool: {str(e)}",
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
                messages.append(tool_message)
