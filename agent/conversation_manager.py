"""
Conversation Manager - Orchestrates AI chat sessions with Redis-backed persistence.

Execution Flow Map:
• create_conversation → generates UUID, initializes empty message list, persists to Redis
• list_conversations → fetches sorted set from Redis, returns summaries (no messages)
• get_conversation / delete_conversation → direct Redis key operations
• chat → entry point: loads history, prepends system prompt if new, delegates to stream/non-stream
• _stream_chat → yields SSE chunks via DialClient, saves messages after completion
• _non_stream_chat → awaits full response, appends AI message, saves and returns dict
• _save_conversation_messages / _save_conversation → serialize messages to Redis, update timestamp

External I/O: Redis (async) for persistence, DialClient for LLM calls (may involve MCP tool calls).
Error paths: raises if conversation not found; Redis/network errors propagate to caller.
"""
import json
import logging
import uuid
from datetime import datetime, UTC
from typing import Optional, AsyncGenerator

import redis.asyncio as redis

from agent.clients.dial_client import DialClient
from agent.models.message import Message, Role
from agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Redis key patterns:
# - Individual conversation: "conversation:{uuid}" → JSON blob with messages
# - Sorted set index: "conversations:list" → scores are timestamps for ordering
CONVERSATION_PREFIX = "conversation:"
CONVERSATION_LIST_KEY = "conversations:list"


class ConversationManager:
    """
    Manages conversation lifecycle including AI interactions and persistence.
    
    Responsibilities:
    - CRUD operations for conversations stored in Redis
    - Orchestrating chat flow: history retrieval → LLM call → persistence
    - Supporting both streaming (SSE) and non-streaming response modes
    """

    def __init__(self, dial_client: DialClient, redis_client: redis.Redis):
        """
        Initialize the manager with required clients.
        
        Args:
            dial_client: Handles LLM communication and tool calling loop.
            redis_client: Async Redis client for conversation persistence.
        """
        self.dial_client = dial_client
        self.redis = redis_client
        logger.info("ConversationManager initialized")

    async def create_conversation(self, title: str) -> dict:
        """
        Create a new conversation with empty message history.
        
        Args:
            title: Display name for the conversation (shown in UI sidebar).
            
        Returns:
            dict: Full conversation object with id, title, messages, timestamps.
            
        Side effects:
            - Writes conversation JSON to Redis key "conversation:{id}"
            - Adds id to sorted set for chronological listing
        """
        conversation_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        
        conversation = {
            "id": conversation_id,
            "title": title,
            "messages": [],  # Starts empty; system prompt added on first chat()
            "created_at": created_at,
            "updated_at": created_at
        }
        
        # Persist conversation data as JSON string
        await self.redis.set(
            f"{CONVERSATION_PREFIX}{conversation_id}",
            json.dumps(conversation)
        )
        
        # Add to sorted set for list_conversations ordering (score = timestamp)
        await self.redis.zadd(
            CONVERSATION_LIST_KEY,
            {conversation_id: datetime.now(UTC).timestamp()}
        )
        
        logger.info(f"Created conversation {conversation_id}: {title}")
        return conversation

    async def list_conversations(self) -> list[dict]:
        """
        List all conversations sorted by last update time (newest first).
        
        Returns:
            list[dict]: Conversation summaries (id, title, timestamps, message_count).
                        Does NOT include full message history for efficiency.
        """
        # zrevrange returns IDs ordered by score descending (most recent first)
        conversation_ids = await self.redis.zrevrange(CONVERSATION_LIST_KEY, 0, -1)
        
        conversations = []
        for conversation_id in conversation_ids:
            conv_data = await self.redis.get(f"{CONVERSATION_PREFIX}{conversation_id}")
            if conv_data:
                conv = json.loads(conv_data)
                # Return summary only - omit messages array to reduce payload
                conversations.append({
                    "id": conv["id"],
                    "title": conv["title"],
                    "created_at": conv["created_at"],
                    "updated_at": conv["updated_at"],
                    "message_count": len(conv["messages"])
                })
        
        return conversations

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """
        Retrieve a conversation by ID, including full message history.
        
        Args:
            conversation_id: UUID of the conversation.
            
        Returns:
            dict | None: Full conversation object, or None if not found.
        """
        conv_data = await self.redis.get(f"{CONVERSATION_PREFIX}{conversation_id}")
        if not conv_data:
            return None
        
        conversation = json.loads(conv_data)
        return conversation

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Remove a conversation from Redis.
        
        Args:
            conversation_id: UUID of the conversation to delete.
            
        Returns:
            bool: True if conversation existed and was deleted, False otherwise.
            
        Side effects:
            - Deletes conversation:{id} key
            - Removes id from conversations:list sorted set
        """
        deleted_count = await self.redis.delete(f"{CONVERSATION_PREFIX}{conversation_id}")
        await self.redis.zrem(CONVERSATION_LIST_KEY, conversation_id)
        return deleted_count > 0

    async def chat(
            self,
            user_message: Message,
            conversation_id: str,
            stream: bool = False
    ):
        """
        Main entry point: process user message and generate AI response.
        
        Args:
            user_message: The user's input Message object.
            conversation_id: UUID of existing conversation.
            stream: If True, returns an async generator for SSE streaming.
                    If False, returns a dict with full response.
                    
        Returns:
            AsyncGenerator[str, None] (stream=True) or dict (stream=False).
            
        Raises:
            ValueError: If conversation_id does not exist in Redis.
            
        Flow:
            1. Load conversation history from Redis
            2. Reconstruct Message objects from stored dicts
            3. Prepend system prompt if this is the first message
            4. Append user_message to history
            5. Delegate to streaming or non-streaming handler
        """
        # TODO: Implementation steps:
        # 1. Log the incoming request for debugging
        # 2. Get conversation (use method `get_conversation`)
        # 3. Raise ValueError if conversation is not found
        # 4. Reconstruct messages: iterate conv["messages"], create Message(**msg_data) for each
        # 5. If messages list is empty → new conversation → prepend system prompt Message
        # 6. Append user_message to messages list
        # 7. Return: _stream_chat(...) if stream else await _non_stream_chat(...)
        raise NotImplementedError()


    async def _stream_chat(
            self,
            conversation_id: str,
            messages: list[Message],
    ) -> AsyncGenerator[str, None]:
        """
        Handle streaming chat: yields SSE chunks, saves state after completion.
        
        Args:
            conversation_id: UUID for persistence after streaming completes.
            messages: Full message history including latest user message.
                      NOTE: DialClient.stream_response mutates this list,
                      appending tool results and final assistant message.
                      
        Yields:
            str: SSE-formatted chunks ("data: {...}\n\n").
            
        Side effects:
            - Persists final messages array to Redis after stream exhausted.
        """
        # First chunk: send conversation_id so client can track which conversation
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
        
        # Stream LLM response chunks; dial_client handles tool calling loop internally
        async for chunk in self.dial_client.stream_response(messages):
            yield chunk
        
        # After streaming completes, persist the updated messages (includes AI response)
        await self._save_conversation_messages(conversation_id, messages)

    async def _non_stream_chat(
            self,
            conversation_id: str,
            messages: list[Message],
    ) -> dict:
        """
        Handle non-streaming chat: waits for full response, then saves.
        
        Args:
            conversation_id: UUID for persistence.
            messages: Message history (user message already appended by chat()).
            
        Returns:
            dict: {"content": str, "conversation_id": str} for JSON response.
        """
        # Get complete AI response (may involve multiple tool calls internally)
        ai_message = await self.dial_client.response(messages)
        messages.append(ai_message)
        
        # Persist updated history
        await self._save_conversation_messages(conversation_id, messages)
        
        return {
            "content": ai_message.content or '',
            "conversation_id": conversation_id
        }

    async def _save_conversation_messages(
            self,
            conversation_id: str,
            messages: list[Message]
    ):
        """
        Serialize Message objects and persist to Redis.
        
        Args:
            conversation_id: UUID of conversation to update.
            messages: List of Message objects to serialize.
            
        Assumes:
            Conversation already exists in Redis (created via create_conversation).
        """
        conv_data = await self.redis.get(f"{CONVERSATION_PREFIX}{conversation_id}")
        conversation = json.loads(conv_data)
        
        # Convert Message objects to dicts for JSON serialization
        conversation["messages"] = [msg.model_dump() for msg in messages]
        conversation["updated_at"] = datetime.now(UTC).isoformat()
        
        await self._save_conversation(conversation)

    async def _save_conversation(self, conversation: dict):
        """
        Low-level persistence: writes conversation dict to Redis.
        
        Args:
            conversation: Full conversation dict (must include "id").
            
        Side effects:
            - Overwrites conversation:{id} key with new JSON
            - Updates sorted set score to current timestamp (bumps to top of list)
        """
        conversation_id = conversation["id"]
        
        # Overwrite the full conversation JSON
        await self.redis.set(
            f"{CONVERSATION_PREFIX}{conversation_id}",
            json.dumps(conversation)
        )
        
        # Update score in sorted set so list_conversations shows most recent first
        await self.redis.zadd(
            CONVERSATION_LIST_KEY,
            {conversation_id: datetime.now(UTC).timestamp()}
        )
