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
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
            self,
            api_key: str,
            endpoint: str,
            model: str,
            tools: list[dict[str, Any]],
            tool_name_client_map: dict[str, HttpMCPClient | StdioMCPClient]
    ):
        self.tools = tools
        self.tool_name_client_map = tool_name_client_map
        self.model = model
        self.async_openai = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=""
        )

    async def response(self, messages: list[Message]) -> Message:
        """Non-streaming completion with tool calling support"""
        response = await self.async_openai.chat.completions.create(
            model=self.model,
            messages=[msg.to_dict() for msg in messages],
            tools=self.tools if self.tools else None
        )
        
        ai_message = Message(
            role=Role.ASSISTANT,
            content=response.choices[0].message.content
        )
        
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
        
        if ai_message.tool_calls:
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
            return await self.response(messages)
        
        return ai_message

    async def stream_response(self, messages: list[Message]) -> AsyncGenerator[str, None]:
        """
        Streaming completion with tool calling support.
        Yields SSE-formatted chunks.
        """
        #TODO:
        # 1. Create chat completions request (self.async_openai.chat.completions.create) and get it as `stream`
        # 2. Create empty sting and assign it to `content_buffer` variable (we will collect content while streaming)
        # 3. Create empty array with `tool_deltas` variable name
        # 4. Make async loop through `stream` (async for chunk in stream):
        #       - get delta chunk
        #       - if delta contains content
        #           - create dict:{"choices": [{"delta": {"content": delta.content}, "index": 0, "finish_reason": None}]} as `chunk_data`
        #           - `yield f"data: {json.dumps(chunk_data)}\n\n"`
        #           - concat `content_buffer` with delta content
        #       - if delta has tool calls then extend `tool_deltas` with `delta.tool_calls`
        # 5. If `tool_deltas` are present:
        #       - collect tool calls with `_collect_tool_calls` method and assign to the `tool_calls` variable
        #       - create assistant message with collected content and tool calls
        #       - add created assistant message to `messages`
        #       - call `_call_tools(ai_message, messages)` (its async, don't forget about await)
        #       - make recursive call with messages to process further:
        #           `async for chunk in self.stream_response(messages):
        #               yield chunk
        #            return`
        # 6. Add assistant message with collected content
        # 7. Create final chunk dict: {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}
        # 8. yield f"data: {json.dumps(final_chunk)}\n\n"
        # 9. yield "data: [DONE]\n\n"
        raise NotImplementedError()

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(lambda: {
            "id": None,
            "function": {"arguments": "", "name": None},
            "type": None
        })
        
        for delta in tool_deltas:
            idx = delta.index
            if delta.id:
                tool_dict[idx]["id"] = delta.id
            if delta.function and delta.function.name:
                tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function and delta.function.arguments:
                tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type:
                tool_dict[idx]["type"] = delta.type
        
        return list(tool_dict.values())

    async def _call_tools(self, ai_message: Message, messages: list[Message], silent: bool = False):
        """Execute tool calls using MCP client"""
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            
            mcp_client = self.tool_name_client_map.get(tool_name)
            
            if not mcp_client:
                tool_message = Message(
                    role=Role.TOOL,
                    content=f"Error: Tool '{tool_name}' not found",
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
                messages.append(tool_message)
                continue
            
            try:
                result = await mcp_client.call_tool(tool_name, tool_args)
                tool_message = Message(
                    role=Role.TOOL,
                    content=str(result),
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
                messages.append(tool_message)
            except Exception as e:
                logger.error(f"Error calling tool {tool_name}: {e}")
                tool_message = Message(
                    role=Role.TOOL,
                    content=f"Error executing tool: {str(e)}",
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
                messages.append(tool_message)
