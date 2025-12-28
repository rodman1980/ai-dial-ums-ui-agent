import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from agent.clients.dial_client import DialClient
from agent.clients.http_mcp_client import HttpMCPClient
from agent.clients.stdio_mcp_client import StdioMCPClient
from agent.conversation_manager import ConversationManager
from agent.models.message import Message

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

conversation_manager: Optional[ConversationManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP clients, Redis, and ConversationManager on startup"""
    global conversation_manager

    logger.info("Application startup initiated")

    tools = []
    tool_name_client_map = {}
    
    # Initialize UMS MCP Client
    ums_mcp_client = await HttpMCPClient.create("http://localhost:8005/mcp")
    ums_tools = await ums_mcp_client.get_tools()
    for tool in ums_tools:
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = ums_mcp_client
    
    # Initialize Fetch MCP Client
    fetch_mcp_client = await HttpMCPClient.create("https://remote.mcpservers.org/fetch/mcp")
    fetch_tools = await fetch_mcp_client.get_tools()
    for tool in fetch_tools:
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = fetch_mcp_client
    
    # Initialize DuckDuckGo MCP Client
    duckduckgo_mcp_client = await StdioMCPClient.create("mcp/duckduckgo:latest")
    duckduckgo_tools = await duckduckgo_mcp_client.get_tools()
    for tool in duckduckgo_tools:
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = duckduckgo_mcp_client
    
    # Initialize DIAL Client
    dial_client = DialClient(
        api_key=os.getenv("DIAL_API_KEY", ""),
        endpoint="https://ai-proxy.lab.epam.com",
        model="gpt-4o",
        tools=tools,
        tool_name_client_map=tool_name_client_map
    )
    
    # Initialize Redis client
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True
    )
    await redis_client.ping()
    logger.info("Redis connection successful")
    
    # Initialize ConversationManager
    conversation_manager = ConversationManager(dial_client, redis_client)
    logger.info("Application startup complete")
    
    yield


app = FastAPI(
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Request/Response Models
class ChatRequest(BaseModel):
    message: Message
    stream: bool = True


class ChatResponse(BaseModel):
    content: str
    conversation_id: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class CreateConversationRequest(BaseModel):
    title: str = None


# Endpoints
@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "conversation_manager_initialized": conversation_manager is not None
    }


@app.post("/conversations")
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation"""
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    title = request.title or "New Conversation"
    conversation = await conversation_manager.create_conversation(title)
    return conversation


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations():
    """List all conversations"""
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    conversations = await conversation_manager.list_conversations()
    return conversations


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation"""
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    conversation = await conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    deleted = await conversation_manager.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation deleted successfully"}


@app.post("/conversations/{conversation_id}/chat")
async def chat(conversation_id: str, request: ChatRequest):
    """Chat endpoint that processes messages and returns assistant response"""
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    try:
        result = await conversation_manager.chat(
            user_message=request.message,
            conversation_id=conversation_id,
            stream=request.stream
        )
        
        if request.stream:
            return StreamingResponse(result, media_type="text/event-stream")
        else:
            return ChatResponse(**result)
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting UMS Agent server")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8011,
        log_level="debug"
    )