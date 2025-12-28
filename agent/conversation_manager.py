import json
import logging
import os
import uuid
from datetime import datetime, UTC
from typing import Optional, AsyncGenerator

import redis.asyncio as redis

from agent.clients.dial_client import DialClient
from agent.models.message import Message, Role
from agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

CONVERSATION_PREFIX = "conversation:"
CONVERSATION_LIST_KEY = "conversations:list"


class ConversationManager:
    """Manages conversation lifecycle including AI interactions and persistence"""

    def __init__(self, dial_client: DialClient, redis_client: redis.Redis):
        self.dial_client = dial_client
        self.redis = redis_client
        logger.info("ConversationManager initialized")

    async def create_conversation(self, title: str) -> dict:
        """Create a new conversation"""
        conversation_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        
        conversation = {
            "id": conversation_id,
            "title": title,
            "messages": [],
            "created_at": created_at,
            "updated_at": created_at
        }
        
        await self.redis.set(
            f"{CONVERSATION_PREFIX}{conversation_id}",
            json.dumps(conversation)
        )
        
        await self.redis.zadd(
            CONVERSATION_LIST_KEY,
            {conversation_id: datetime.now(UTC).timestamp()}
        )
        
        logger.info(f"Created conversation {conversation_id}: {title}")
        return conversation

    async def list_conversations(self) -> list[dict]:
        """List all conversations sorted by last update time"""
        conversation_ids = await self.redis.zrevrange(CONVERSATION_LIST_KEY, 0, -1)
        
        conversations = []
        for conversation_id in conversation_ids:
            conv_data = await self.redis.get(f"{CONVERSATION_PREFIX}{conversation_id}")
            if conv_data:
                conv = json.loads(conv_data)
                conversations.append({
                    "id": conv["id"],
                    "title": conv["title"],
                    "created_at": conv["created_at"],
                    "updated_at": conv["updated_at"],
                    "message_count": len(conv["messages"])
                })
        
        return conversations

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get a specific conversation"""
        conv_data = await self.redis.get(f"{CONVERSATION_PREFIX}{conversation_id}")
        if not conv_data:
            return None
        
        conversation = json.loads(conv_data)
        return conversation

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
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
        Process chat messages and return AI response.
        Automatically saves conversation state.
        """
        #TODO:
        # 1. Log request
        # 2. Get conversation (use method `get_conversation`)
        # 3. Raise an error that no conversation foud if conversation is not present
        # 4. Get `messages` from conversation, iterate through them and create array with `Message(**msg_data)`
        # 5. If `messages` array is empty it means that it is beginning of the conversation. Add system prompt as 1st message
        # 6. Agge `user_message` to `messages` array
        # 7. If `stream` is true then call `_stream_chat` (without await!), otherwise call `_non_stream_chat` (with await) and return it
        raise NotImplementedError()


    async def _stream_chat(
            self,
            conversation_id: str,
            messages: list[Message],
    ) -> AsyncGenerator[str, None]:
        """Handle streaming chat with automatic saving"""
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
        
        async for chunk in self.dial_client.stream_response(messages):
            yield chunk
        
        await self._save_conversation_messages(conversation_id, messages)

    async def _non_stream_chat(
            self,
            conversation_id: str,
            messages: list[Message],
    ) -> dict:
        """Handle non-streaming chat"""
        ai_message = await self.dial_client.response(messages)
        messages.append(ai_message)
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
        """Save or update conversation messages"""
        conv_data = await self.redis.get(f"{CONVERSATION_PREFIX}{conversation_id}")
        conversation = json.loads(conv_data)
        
        conversation["messages"] = [msg.model_dump() for msg in messages]
        conversation["updated_at"] = datetime.now(UTC).isoformat()
        
        await self._save_conversation(conversation)

    async def _save_conversation(self, conversation: dict):
        """Internal method to persist conversation to Redis"""
        conversation_id = conversation["id"]
        
        await self.redis.set(
            f"{CONVERSATION_PREFIX}{conversation_id}",
            json.dumps(conversation)
        )
        
        await self.redis.zadd(
            CONVERSATION_LIST_KEY,
            {conversation_id: datetime.now(UTC).timestamp()}
        )
