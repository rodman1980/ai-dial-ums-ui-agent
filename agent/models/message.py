"""
Message models for LLM conversation flow.
Defines roles and message structure compatible with OpenAI/DIAL chat format.
"""
from enum import StrEnum
from typing import Any
from pydantic import BaseModel


class Role(StrEnum):
    """
    Chat message roles in the conversation chain.
    Maps to OpenAI/DIAL API message roles for LLM interactions.
    """
    SYSTEM = "system"      # System instructions/context
    USER = "user"          # User-generated messages
    ASSISTANT = "assistant"  # LLM-generated responses
    TOOL = "tool"          # Tool execution results


class Message(BaseModel):
    """
    Unified message format for LLM conversations with tool calling support.
    
    Supports both standard chat messages and tool-related messages:
    - User/Assistant messages: use role + content
    - Tool calls: assistant message with tool_calls list
    - Tool results: tool role with tool_call_id + content + name
    
    Compatible with OpenAI/DIAL API format via to_dict() serialization.
    """
    role: Role
    content: str | None = None  # Message text; None allowed for tool calls
    tool_call_id: str | None = None  # Required for tool role messages
    name: str | None = None  # Tool name for tool role messages
    tool_calls: list[dict[str, Any]] | None = None  # Assistant's tool invocations

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize message to OpenAI/DIAL API format.
        
        Returns:
            dict: Message with only non-None fields included to minimize payload size
        """
        result = {"role": str(self.role.value)}
        
        # Include only populated fields to avoid sending null values to API
        if self.content:
            result["content"] = self.content
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
            
        return result
