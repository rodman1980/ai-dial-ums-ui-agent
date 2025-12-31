---
title: API Reference
description: Complete API documentation for endpoints, request/response models, and client interfaces
version: 1.0.0
last_updated: 2025-12-30
related: [architecture.md, README.md]
tags: [api, fastapi, openapi, endpoints]
---

# API Reference

## Table of Contents

- [Overview](#overview)
- [Base Configuration](#base-configuration)
- [REST Endpoints](#rest-endpoints)
- [Models](#models)
- [Client Interfaces](#client-interfaces)
- [Error Handling](#error-handling)

## Overview

The Users Management Agent exposes a FastAPI-based REST API with support for both streaming (SSE) and non-streaming responses. All endpoints return JSON except streaming chat responses.

### OpenAPI Documentation

Interactive API documentation available at:
- **Swagger UI**: `http://localhost:8011/docs`
- **ReDoc**: `http://localhost:8011/redoc`
- **OpenAPI JSON**: `http://localhost:8011/openapi.json`

## Base Configuration

### Server

```yaml
Base URL: http://localhost:8011
Protocol: HTTP/1.1
Default Port: 8011
CORS: * (all origins - development only)
```

### Headers

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | POST/PUT requests |
| `Accept` | `application/json` or `text/event-stream` | All requests |

### Authentication

⚠️ **None** - Authentication explicitly skipped for this workshop project.

Production deployment would require:
- Bearer token authentication
- API key validation
- Rate limiting per user

## REST Endpoints

### Health Check

Check application health and initialization status.

```http
GET /health
```

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "conversation_manager_initialized": true
}
```

**Use Cases**:
- Startup verification
- Load balancer health checks
- Monitoring probes

**Example**:
```bash
curl http://localhost:8011/health
```

---

### Create Conversation

Initialize a new conversation with unique ID.

```http
POST /conversations
```

**Request Body**:
```json
{
  "title": "New Conversation"  // Optional, defaults to "New Conversation"
}
```

**Response** `200 OK`:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "New Conversation",
  "messages": [],
  "created_at": "2025-12-30T10:15:00.000Z",
  "updated_at": "2025-12-30T10:15:00.000Z"
}
```

**Errors**:
- `500 Internal Server Error`: ConversationManager not initialized

**Example**:
```bash
curl -X POST http://localhost:8011/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "User Management Questions"}'
```

**Code Reference**: [app.py#L150](../agent/app.py)

---

### List Conversations

Retrieve all conversations sorted by most recently updated.

```http
GET /conversations
```

**Response** `200 OK`:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "User Management Questions",
    "created_at": "2025-12-30T10:15:00.000Z",
    "updated_at": "2025-12-30T10:30:00.000Z",
    "message_count": 12
  },
  {
    "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "title": "Web Search Test",
    "created_at": "2025-12-29T14:20:00.000Z",
    "updated_at": "2025-12-29T14:45:00.000Z",
    "message_count": 8
  }
]
```

**Notes**:
- Sorted by `updated_at` descending (newest first)
- Messages array NOT included (use Get Conversation for full history)
- Returns empty array `[]` if no conversations exist

**Example**:
```bash
curl http://localhost:8011/conversations
```

**Code Reference**: [app.py#L170](../agent/app.py)

---

### Get Conversation

Retrieve full conversation including all messages.

```http
GET /conversations/{conversation_id}
```

**Path Parameters**:
- `conversation_id` (string, UUID): Conversation identifier

**Response** `200 OK`:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "User Management Questions",
  "messages": [
    {
      "role": "system",
      "content": "You are a User Management Assistant..."
    },
    {
      "role": "user",
      "content": "Show me all users"
    },
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "search_users",
            "arguments": "{}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "content": "[{\"id\": 1, \"name\": \"John Doe\"}]",
      "tool_call_id": "call_abc123",
      "name": "search_users"
    },
    {
      "role": "assistant",
      "content": "Here are all users: ..."
    }
  ],
  "created_at": "2025-12-30T10:15:00.000Z",
  "updated_at": "2025-12-30T10:30:00.000Z"
}
```

**Response** `404 Not Found`:
```json
{
  "detail": "Conversation not found"
}
```

**Example**:
```bash
curl http://localhost:8011/conversations/550e8400-e29b-41d4-a716-446655440000
```

**Code Reference**: [app.py#L182](../agent/app.py)

---

### Delete Conversation

Permanently remove a conversation and all its messages.

```http
DELETE /conversations/{conversation_id}
```

**Path Parameters**:
- `conversation_id` (string, UUID): Conversation identifier

**Response** `200 OK`:
```json
{
  "success": true
}
```

**Response** `404 Not Found`:
```json
{
  "detail": "Conversation not found"
}
```

**Example**:
```bash
curl -X DELETE http://localhost:8011/conversations/550e8400-e29b-41d4-a716-446655440000
```

**Code Reference**: [app.py#L197](../agent/app.py)

---

### Chat (Non-Streaming)

Send a message and receive complete response.

```http
POST /conversations/{conversation_id}/chat
```

**Path Parameters**:
- `conversation_id` (string, UUID): Conversation identifier

**Request Body**:
```json
{
  "message": {
    "role": "user",
    "content": "Show me all active users"
  },
  "stream": false
}
```

**Response** `200 OK`:
```json
{
  "content": "Here are all active users: ...",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors**:
- `404 Not Found`: Conversation doesn't exist
- `500 Internal Server Error`: LLM or MCP error

**Flow**:
1. Load conversation history from Redis
2. Append user message
3. Call LLM with tool support
4. Execute any tool calls recursively
5. Save updated conversation
6. Return final response

**Example**:
```bash
curl -X POST http://localhost:8011/conversations/550e8400-e29b-41d4-a716-446655440000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"role": "user", "content": "List all users"},
    "stream": false
  }'
```

**Code Reference**: [app.py#L214](../agent/app.py)

---

### Chat (Streaming)

Send a message and receive Server-Sent Events (SSE) stream.

```http
POST /conversations/{conversation_id}/chat
```

**Path Parameters**:
- `conversation_id` (string, UUID): Conversation identifier

**Request Body**:
```json
{
  "message": {
    "role": "user",
    "content": "Tell me about user John Doe"
  },
  "stream": true
}
```

**Response** `200 OK` (Content-Type: `text/event-stream`):
```
data: {"conversation_id": "550e8400-e29b-41d4-a716-446655440000"}

data: {"choices": [{"delta": {"content": "Let"}, "index": 0, "finish_reason": null}]}

data: {"choices": [{"delta": {"content": " me"}, "index": 0, "finish_reason": null}]}

data: {"choices": [{"delta": {"content": " search"}, "index": 0, "finish_reason": null}]}

data: {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}

data: [DONE]
```

**SSE Event Format**:

Each event follows Server-Sent Events specification:
```
data: <JSON payload>\n\n
```

**First Event** (always sent):
```json
{"conversation_id": "uuid"}
```

**Content Delta Events**:
```json
{
  "choices": [{
    "delta": {"content": "text chunk"},
    "index": 0,
    "finish_reason": null
  }]
}
```

**Final Event**:
```json
{
  "choices": [{
    "delta": {},
    "index": 0,
    "finish_reason": "stop"
  }]
}
```

**Stream Terminator**:
```
data: [DONE]\n\n
```

**Example (JavaScript)**:
```javascript
const response = await fetch('http://localhost:8011/conversations/{id}/chat', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    message: {role: 'user', content: 'Hello'},
    stream: true
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6);
      if (data === '[DONE]') return;
      
      const parsed = JSON.parse(data);
      if (parsed.choices?.[0]?.delta?.content) {
        console.log(parsed.choices[0].delta.content);
      }
    }
  }
}
```

**Code Reference**: [app.py#L214](../agent/app.py)

---

## Models

### Message

Represents a single message in a conversation.

**Python Definition**: [agent/models/message.py](../agent/models/message.py)

```python
class Message(BaseModel):
    role: Role  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_call_id: str | None = None  # Required for role="tool"
    name: str | None = None  # Tool name for role="tool"
    tool_calls: list[dict[str, Any]] | None = None  # For assistant role
```

**JSON Schema**:
```json
{
  "role": "user",
  "content": "Show me all users",
  "tool_call_id": null,
  "name": null,
  "tool_calls": null
}
```

**Role Types**:

| Role | Usage | Required Fields |
|------|-------|----------------|
| `system` | System prompt (first message) | `content` |
| `user` | User input | `content` |
| `assistant` | LLM response | `content` (or `tool_calls`) |
| `tool` | Tool execution result | `content`, `tool_call_id`, `name` |

**Tool Call Format**:
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "search_users",
        "arguments": "{\"query\": \"active\"}"
      }
    }
  ]
}
```

---

### ChatRequest

Request body for chat endpoints.

```typescript
interface ChatRequest {
  message: Message;
  stream?: boolean;  // Default: true
}
```

**Example**:
```json
{
  "message": {
    "role": "user",
    "content": "Find user by email john@example.com"
  },
  "stream": true
}
```

---

### ChatResponse

Response body for non-streaming chat.

```typescript
interface ChatResponse {
  content: string;
  conversation_id: string;
}
```

**Example**:
```json
{
  "content": "I found the user: John Doe (ID: 42)",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### ConversationSummary

Lightweight conversation metadata (used in list endpoint).

```typescript
interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;  // ISO 8601
  updated_at: string;  // ISO 8601
  message_count: number;
}
```

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "User Management Questions",
  "created_at": "2025-12-30T10:15:00.000Z",
  "updated_at": "2025-12-30T10:30:00.000Z",
  "message_count": 12
}
```

---

### Conversation

Full conversation object (used in get/create endpoints).

```typescript
interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;  // ISO 8601
  updated_at: string;  // ISO 8601
}
```

## Client Interfaces

### DialClient

**Purpose**: Wrapper for DIAL API (OpenAI-compatible) with tool calling support.

**Location**: [agent/clients/dial_client.py](../agent/clients/dial_client.py)

#### Constructor

```python
DialClient(
    api_key: str,
    endpoint: str,
    model: str,
    tools: list[dict[str, Any]],
    tool_name_client_map: dict[str, HttpMCPClient | StdioMCPClient]
)
```

**Parameters**:
- `api_key`: DIAL API authentication key
- `endpoint`: DIAL API base URL (e.g., `https://ai-proxy.lab.epam.com`)
- `model`: Model identifier (e.g., `gpt-4o`, `claude-3-7-sonnet@20250219`)
- `tools`: List of tools in DIAL/OpenAI format
- `tool_name_client_map`: Maps tool names to their MCP client executors

#### Methods

##### `async response(messages: list[Message]) -> Message`

Execute non-streaming completion with recursive tool calling.

**Returns**: Final assistant message after all tool calls complete.

**Example**:
```python
final_message = await dial_client.response([
    Message(role=Role.USER, content="Show all users")
])
print(final_message.content)
```

##### `async stream_response(messages: list[Message]) -> AsyncGenerator[str, None]`

Execute streaming completion with tool calling support.

**Yields**: SSE-formatted chunks (`data: {...}\n\n`)

**Example**:
```python
async for chunk in dial_client.stream_response(messages):
    print(chunk, end='')
```

---

### HttpMCPClient

**Purpose**: Connect to HTTP/SSE-based MCP servers.

**Location**: [agent/clients/http_mcp_client.py](../agent/clients/http_mcp_client.py)

#### Factory Method

```python
client = await HttpMCPClient.create(mcp_server_url: str)
```

**Parameters**:
- `mcp_server_url`: Full HTTP URL (e.g., `http://localhost:8005/mcp`)

**Returns**: Initialized and connected client.

#### Methods

##### `async get_tools() -> list[dict[str, Any]]`

Retrieve available tools in DIAL/OpenAI format.

**Returns**: List of tool definitions.

**Example**:
```python
tools = await client.get_tools()
print(tools[0]['function']['name'])  # "search_users"
```

##### `async call_tool(tool_name: str, tool_args: dict[str, Any]) -> Any`

Execute a tool on the MCP server.

**Returns**: String (for TextContent) or raw content list.

**Example**:
```python
result = await client.call_tool("search_users", {"query": "active"})
print(result)  # "[{\"id\": 1, \"name\": \"John\"}]"
```

---

### StdioMCPClient

**Purpose**: Connect to Docker stdio-based MCP servers.

**Location**: [agent/clients/stdio_mcp_client.py](../agent/clients/stdio_mcp_client.py)

#### Factory Method

```python
client = await StdioMCPClient.create(docker_image: str)
```

**Parameters**:
- `docker_image`: Docker image name (e.g., `mcp/duckduckgo:latest`)

**Returns**: Initialized and connected client.

#### Methods

Same as `HttpMCPClient` (see above).

---

### ConversationManager

**Purpose**: Orchestrate chat flow and Redis persistence.

**Location**: [agent/conversation_manager.py](../agent/conversation_manager.py)

#### Constructor

```python
ConversationManager(
    dial_client: DialClient,
    redis_client: redis.Redis
)
```

#### Methods

##### `async create_conversation(title: str) -> dict`

Create new conversation with UUID.

##### `async list_conversations() -> list[dict]`

List all conversations (summaries only).

##### `async get_conversation(conversation_id: str) -> Optional[dict]`

Load full conversation including messages.

##### `async delete_conversation(conversation_id: str) -> bool`

Delete conversation from Redis.

##### `async chat(user_message: Message, conversation_id: str, stream: bool = False)`

Main entry point for chat interactions.

**Returns**: `AsyncGenerator[str, None]` (stream=True) or `dict` (stream=False).

---

## Error Handling

### Standard Error Response

All errors return JSON with `detail` field:

```json
{
  "detail": "Error message"
}
```

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| `200` | Success | All successful operations |
| `404` | Not Found | Conversation doesn't exist |
| `500` | Internal Server Error | LLM/MCP/Redis errors, initialization failures |

### Error Examples

**Conversation Not Found**:
```json
{
  "detail": "Conversation not found"
}
```

**Manager Not Initialized**:
```json
{
  "detail": "Conversation manager not initialized"
}
```

### Client-Side Error Handling

**JavaScript Example**:
```javascript
try {
  const response = await fetch('/conversations/invalid-id');
  if (!response.ok) {
    const error = await response.json();
    console.error(`Error ${response.status}: ${error.detail}`);
  }
} catch (err) {
  console.error('Network error:', err);
}
```

**Python Example**:
```python
import httpx

try:
    response = httpx.get("http://localhost:8011/conversations/invalid-id")
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    error = e.response.json()
    print(f"Error {e.response.status_code}: {error['detail']}")
```

---

## Rate Limiting

⚠️ **None** - No rate limiting implemented in this workshop project.

Production considerations:
- DIAL API has its own rate limits
- Implement per-user/IP rate limiting
- Add request queuing for burst protection

---

## CORS Configuration

**Current**: `allow_origins=["*"]` (all origins)

**Production**: Restrict to specific domains:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"]
)
```

---

**Next Steps**: Review [Setup Guide](./setup.md) for environment configuration and [Testing Guide](./testing.md) for validation procedures.
