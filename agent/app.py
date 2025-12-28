"""FastAPI application entry point for the UMS Tool Use Agent.

Orchestrates MCP client initialization, conversation management via Redis persistence,
and streaming chat endpoints with LLM tool calling capabilities.
"""

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

# Global state: initialized during lifespan startup, used by all endpoints
conversation_manager: Optional[ConversationManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP clients, Redis, and ConversationManager on startup.
    
    Flow:
    1. Connects to three MCP servers (UMS HTTP, Fetch HTTP, DuckDuckGo stdio)
    2. Aggregates tools from all servers into unified tool list
    3. Maps tool names to their respective MCP clients for execution routing
    4. Initializes DialClient with aggregated tools for LLM tool calling
    5. Establishes Redis connection for conversation persistence
    6. Creates ConversationManager to orchestrate chat sessions
    
    Yields control to FastAPI, then cleans up on shutdown.
    """
    global conversation_manager

    logger.info("Application startup initiated")

    # Aggregated tool registry and routing map for multi-MCP setup
    tools = []
    tool_name_client_map = {}
    
    # Initialize UMS MCP Client (HTTP-based, local user management API)
    ums_mcp_client = await HttpMCPClient.create("http://localhost:8005/mcp")
    ums_tools = await ums_mcp_client.get_tools()
    for tool in ums_tools:
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = ums_mcp_client
    
    # Initialize Fetch MCP Client (HTTP-based, remote web fetching capabilities)
    fetch_mcp_client = await HttpMCPClient.create("https://remote.mcpservers.org/fetch/mcp")
    fetch_tools = await fetch_mcp_client.get_tools()
    for tool in fetch_tools:
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = fetch_mcp_client
    
    # Initialize DuckDuckGo MCP Client (stdio-based, runs via Docker container)
    duckduckgo_mcp_client = await StdioMCPClient.create("mcp/duckduckgo:latest")
    duckduckgo_tools = await duckduckgo_mcp_client.get_tools()
    for tool in duckduckgo_tools:
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = duckduckgo_mcp_client
    
    # Initialize DIAL Client (wraps OpenAI-compatible API with tool calling loop)
    # Requires EPAM VPN for proxy access; uses aggregated tools from all MCP servers
    dial_client = DialClient(
        api_key=os.getenv("DIAL_API_KEY", ""),
        endpoint="https://ai-proxy.lab.epam.com",
        model="gpt-4o",
        tools=tools,
        tool_name_client_map=tool_name_client_map
    )
    
    # Initialize Redis client (conversation persistence layer)
    # decode_responses=True returns strings instead of bytes for easier JSON handling
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True
    )
    await redis_client.ping()  # Verify connectivity early to fail fast
    logger.info("Redis connection successful")
    
    # Initialize ConversationManager (orchestrates chat flow with Redis persistence)
    conversation_manager = ConversationManager(dial_client, redis_client)
    logger.info("Application startup complete")
    
    yield  # Application runs, endpoints use initialized conversation_manager
    
    # TODO: Add cleanup logic for MCP client connections on shutdown


app = FastAPI(
    lifespan=lifespan
)

# Permissive CORS for local development (index.html opened directly in browser)
# WARNING: Restrict origins in production to prevent CSRF attacks
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
    """Health check endpoint for monitoring and startup verification.
    
    Returns:
        dict: Status and initialization state of conversation_manager
        
    Note: Doesn't verify Redis connectivity or MCP client health after startup
    """
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "conversation_manager_initialized": conversation_manager is not None
    }


@app.post("/conversations")
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation with unique ID and initial metadata.
    
    Args:
        request: CreateConversationRequest with optional title
        
    Returns:
        dict: Conversation object with id, title, timestamps, and empty messages list
        
    Raises:
        HTTPException: 500 if conversation_manager not initialized during startup
    """
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    title = request.title or "New Conversation"  # Fallback for empty/missing titles
    conversation = await conversation_manager.create_conversation(title)
    return conversation


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations():
    """List all conversations sorted by most recently updated.
    
    Returns:
        list[ConversationSummary]: Summaries with id, title, timestamps, and message_count
        
    Raises:
        HTTPException: 500 if conversation_manager not initialized
        
    Note: Fetched from Redis sorted set, ordered by updated_at timestamp descending
    """
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    conversations = await conversation_manager.list_conversations()
    return conversations


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with full message history.
    
    Args:
        conversation_id: UUID of the conversation to retrieve
        
    Returns:
        dict: Full conversation object with messages array
        
    Raises:
        HTTPException: 404 if conversation doesn't exist, 500 if manager not initialized
    """
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    conversation = await conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and remove it from Redis.
    
    Args:
        conversation_id: UUID of the conversation to delete
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: 404 if conversation not found, 500 if manager not initialized
    """
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    deleted = await conversation_manager.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation deleted successfully"}


@app.post("/conversations/{conversation_id}/chat")
async def chat(conversation_id: str, request: ChatRequest):
    """Chat endpoint that processes user messages via LLM with tool calling.
    
    Flow:
    1. Validates conversation_manager initialization
    2. Delegates to conversation_manager.chat() which:
       - Appends user message to conversation history in Redis
       - Calls DialClient for LLM inference with tool calling loop
       - Streams SSE chunks or returns full response
       - Persists final assistant response to Redis
    3. Returns StreamingResponse (SSE) or ChatResponse (JSON)
    
    Args:
        conversation_id: UUID of existing conversation
        request: ChatRequest with message and stream flag
        
    Returns:
        StreamingResponse: SSE stream if stream=True (data: {...}\n\n format)
        ChatResponse: JSON with content and conversation_id if stream=False
        
    Raises:
        HTTPException: 404 if conversation not found (ValueError),
                      500 if manager not initialized or unexpected error
    """
    if not conversation_manager:
        raise HTTPException(status_code=500, detail="Conversation manager not initialized")
    
    try:
        result = await conversation_manager.chat(
            user_message=request.message,
            conversation_id=conversation_id,
            stream=request.stream
        )
        
        # stream=True returns async generator for SSE, stream=False returns dict
        if request.stream:
            return StreamingResponse(result, media_type="text/event-stream")
        else:
            return ChatResponse(**result)
    
    except ValueError as e:
        # ValueError raised by conversation_manager when conversation not found
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