---
title: Glossary
description: Domain terms, abbreviations, and technical concepts used in the Users Management Agent project
version: 1.0.0
last_updated: 2025-12-30
related: [README.md, architecture.md]
tags: [glossary, terminology, definitions]
---

# Glossary

## A

**Agent**
: An AI system that autonomously performs tasks by observing its environment, making decisions, and taking actions. In this project, refers to the LLM-driven system that uses tools to manage users.

**Anthropic Format**
: Tool specification format used by Anthropic's Claude API, with structure `{name, description, inputSchema}`. MCP servers return tools in this format.

**API Key**
: Authentication credential required to access the DIAL API. Set via `DIAL_API_KEY` environment variable.

**Async Factory Pattern**
: Design pattern where a class uses an `async classmethod` (e.g., `create()`) instead of `__init__` for initialization requiring async operations. Used by MCP clients.

**AsyncGenerator**
: Python type hint for async generator functions that yield values. Used for streaming responses: `AsyncGenerator[str, None]`.

## C

**CallToolResult**
: MCP protocol type representing the result of a tool execution. Contains a `content` array with text, images, or other data.

**Chat**
: A conversation between a user and the AI agent, consisting of a sequence of messages with roles (system, user, assistant, tool).

**ClientSession**
: MCP protocol class managing bidirectional communication with an MCP server. Handles initialize, list_tools, call_tool, etc.

**Context Manager**
: Python pattern using `with` or `async with` to manage resource lifecycle. Used for MCP connections: `async with stdio_client(...) as streams:`.

**Conversation**
: A persistent chat session with unique UUID, title, message history, and timestamps. Stored in Redis.

**ConversationManager**
: Component orchestrating chat flow, Redis persistence, and coordination between DialClient and storage. See [conversation_manager.py](../agent/conversation_manager.py).

**CORS (Cross-Origin Resource Sharing)**
: Browser security mechanism controlling cross-origin HTTP requests. Configured permissively (`allow_origins=["*"]`) for local development.

**CRUD**
: Create, Read, Update, Delete - basic operations for data management. Applied to conversations in this project.

## D

**Delta**
: In streaming responses, a partial chunk of content. Multiple deltas are concatenated to form complete messages.

**DIAL (Distributed Inference API Layer)**
: EPAM's internal API proxy providing OpenAI-compatible access to multiple LLM providers. Endpoint: `https://ai-proxy.lab.epam.com`.

**DialClient**
: Component wrapping DIAL API with tool calling support and recursive execution. See [dial_client.py](../agent/clients/dial_client.py).

**Docker Compose**
: Tool for defining and running multi-container Docker applications via YAML configuration. Used to start UMS, Redis, and Redis Insight.

**DuckDuckGo MCP**
: Stdio-based MCP server providing web search capabilities via DuckDuckGo. Runs in Docker container `mcp/duckduckgo:latest`.

## E

**Environment Variable**
: OS-level key-value pair used for configuration. Examples: `DIAL_API_KEY`, `REDIS_HOST`, `LOG_LEVEL`.

**EventSource**
: Browser API for receiving Server-Sent Events (SSE). Used by [index.html](../index.html) for streaming responses.

## F

**FastAPI**
: Modern Python web framework for building APIs. Foundation of [app.py](../agent/app.py).

**Fetch MCP**
: HTTP-based MCP server providing web content retrieval. Remote endpoint: `https://remote.mcpservers.org/fetch/mcp`.

**Function Calling**
: LLM capability to invoke external tools/APIs based on natural language instructions. Core pattern of this agent.

## H

**Health Check**
: Endpoint (`/health`) returning application status. Used for monitoring and startup verification.

**HttpMCPClient**
: Client for connecting to HTTP/SSE-based MCP servers. See [http_mcp_client.py](../agent/clients/http_mcp_client.py).

## I

**inputSchema**
: MCP/Anthropic format for tool parameters. JSON Schema defining required/optional arguments. Converted to OpenAI `parameters` format.

**ISO 8601**
: International standard for date/time representation: `2025-12-30T10:15:00.000Z`. Used for conversation timestamps.

## L

**LLM (Large Language Model)**
: AI model trained on vast text data to understand and generate human language. Examples: GPT-4o, Claude-3-7-Sonnet.

**Lifespan**
: FastAPI feature for startup/shutdown logic. Implemented via `@asynccontextmanager` in [app.py](../agent/app.py).

## M

**MCP (Model Context Protocol)**
: Open protocol for connecting LLMs to external tools and data sources. Defines tool discovery, invocation, and response formats.

**MCP Client**
: Component connecting to an MCP server. Two types in this project: `HttpMCPClient` (HTTP/SSE) and `StdioMCPClient` (Docker stdio).

**MCP Server**
: Service exposing tools via MCP protocol. Examples: UMS MCP (user management), Fetch MCP (web content), DuckDuckGo MCP (search).

**Message**
: Single unit in conversation history. Has `role` (system/user/assistant/tool), `content`, and optional `tool_calls`/`tool_call_id`. See [message.py](../agent/models/message.py).

## O

**OpenAI Format**
: Tool specification format used by OpenAI and DIAL APIs: `{type: "function", function: {name, description, parameters}}`.

## P

**Persistence**
: Saving application state to storage (Redis) so it survives restarts. Conversations are persisted as JSON strings.

**PII (Personally Identifiable Information)**
: Data that can identify an individual (name, email, SSN, etc.). Additional Task: implement PII detection/redaction.

**Pydantic**
: Python library for data validation using type annotations. Used for `Message` model and API request/response schemas.

## R

**Redis**
: In-memory data store used for conversation persistence. Stores conversations as JSON strings and maintains sorted set index.

**Redis Insight**
: GUI tool for visualizing Redis data. Access at `http://localhost:6380`.

**Recursive Tool Calling**
: Pattern where LLM can invoke tools, receive results, and decide to call more tools based on results. Implemented via recursion in `DialClient.response()`.

**Role**
: Enum identifying message sender: `SYSTEM`, `USER`, `ASSISTANT`, or `TOOL`. See [message.py](../agent/models/message.py).

## S

**SSE (Server-Sent Events)**
: HTTP-based protocol for server-to-client streaming. Format: `data: {json}\n\n`. Used for streaming chat responses.

**StdioMCPClient**
: Client for connecting to Docker stdio-based MCP servers. Runs `docker run --rm -i <image>` and communicates via stdin/stdout. See [stdio_mcp_client.py](../agent/clients/stdio_mcp_client.py).

**Streaming**
: Delivering response incrementally as it's generated, rather than waiting for completion. Improves perceived responsiveness.

**streamablehttp_client**
: MCP library function creating HTTP/SSE transport for MCP connections. Returns read/write streams.

**stdio_client**
: MCP library function creating Docker stdio transport for MCP connections. Executes Docker command and captures streams.

**System Prompt**
: Initial message with `role: "system"` providing instructions to the LLM. Defines agent capabilities and behavior. See [prompts.py](../agent/prompts.py).

## T

**TextContent**
: MCP protocol type representing plain text content in tool results. Most common result type.

**Tool**
: External function/API callable by the LLM. Examples: `search_users`, `web_search`, `fetch_url`.

**Tool Call**
: LLM's request to invoke a tool. Contains `id`, `type: "function"`, and `function: {name, arguments}`.

**Tool Name Client Map**
: Dictionary mapping tool names to their MCP client executors. Used by `DialClient` to route tool calls: `{"search_users": ums_mcp_client, ...}`.

**Tool Result**
: Message with `role: "tool"` containing output of tool execution. Includes `tool_call_id` to link result to invocation.

**Tool Use Pattern**
: AI agent architecture where LLM orchestrates tool invocations to accomplish tasks. Core pattern of this project.

## U

**UMS (Users Management Service)**
: Mock service providing user CRUD operations. Runs on `http://localhost:8041`.

**UMS MCP Server**
: MCP interface wrapping UMS Service. Exposes user management tools. Runs on `http://localhost:8005/mcp`.

**UUID (Universally Unique Identifier)**
: 128-bit identifier with very low collision probability. Format: `550e8400-e29b-41d4-a716-446655440000`. Used for conversation IDs.

**Uvicorn**
: ASGI server for running FastAPI applications. Command: `uvicorn agent.app:app`.

## V

**VPN (Virtual Private Network)**
: Secure network connection. EPAM VPN required to access DIAL API at `https://ai-proxy.lab.epam.com`.

## W

**Workshop Project**
: Learning-oriented project designed for educational purposes rather than production deployment. This agent is a workshop project.

## Z

**zadd / zrevrange**
: Redis commands for sorted sets. `zadd` adds members with scores; `zrevrange` retrieves members in descending score order. Used for conversation indexing.

---

## Acronym Quick Reference

| Acronym | Full Term | Category |
|---------|-----------|----------|
| ADR | Architecture Decision Record | Documentation |
| AOF | Append-Only File | Redis |
| API | Application Programming Interface | General |
| ASGI | Asynchronous Server Gateway Interface | Python |
| CORS | Cross-Origin Resource Sharing | Security |
| CRUD | Create, Read, Update, Delete | Operations |
| DIAL | Distributed Inference API Layer | EPAM |
| E2E | End-to-End | Testing |
| GUI | Graphical User Interface | UI |
| HTTP | Hypertext Transfer Protocol | Network |
| JSON | JavaScript Object Notation | Data Format |
| LLM | Large Language Model | AI |
| LRU | Least Recently Used | Caching |
| MCP | Model Context Protocol | Protocol |
| PII | Personally Identifiable Information | Security |
| REST | Representational State Transfer | API Style |
| SSE | Server-Sent Events | Protocol |
| UMS | Users Management Service | Domain |
| UUID | Universally Unique Identifier | Data |
| VPN | Virtual Private Network | Network |

---

## See Also

- [Architecture](./architecture.md) - System design and components
- [API Reference](./api.md) - Endpoint specifications
- [Setup Guide](./setup.md) - Installation and configuration
- [ADR Index](./adr/README.md) - Architecture decisions

---

**Note**: This glossary is maintained as terms are introduced in the project. Suggest additions via pull requests.
