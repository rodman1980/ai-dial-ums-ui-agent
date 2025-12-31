---
title: Changelog
description: Version history and notable changes in the Users Management Agent project
version: 1.0.0
last_updated: 2025-12-30
related: [roadmap.md, README.md]
tags: [changelog, versions, history]
---

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- PII detection and redaction module
- Authentication and authorization
- Unit and integration test suite
- CI/CD pipeline
- Comprehensive error handling
- MCP client cleanup on shutdown

---

## [Workshop v1.0] - 2025-12-30

### Added
- **Core Agent Implementation**
  - Tool Use Agent pattern with recursive tool calling
  - Multi-MCP server integration (HTTP and stdio transports)
  - Streaming and non-streaming chat responses
  
- **Infrastructure**
  - Docker Compose setup for UMS, Redis, and Redis Insight
  - FastAPI application with async lifecycle management
  - Redis-backed conversation persistence
  
- **MCP Clients**
  - `HttpMCPClient` for HTTP/SSE-based MCP servers ([http_mcp_client.py](../agent/clients/http_mcp_client.py))
  - `StdioMCPClient` for Docker stdio-based MCP servers ([stdio_mcp_client.py](../agent/clients/stdio_mcp_client.py))
  - Async factory pattern for connection initialization
  - Format conversion (Anthropic → OpenAI/DIAL)
  
- **DIAL Integration**
  - `DialClient` wrapper for DIAL API ([dial_client.py](../agent/clients/dial_client.py))
  - Recursive tool calling loop
  - Streaming response support with SSE
  - Tool routing via `tool_name_client_map`
  
- **Conversation Management**
  - `ConversationManager` for chat orchestration ([conversation_manager.py](../agent/conversation_manager.py))
  - CRUD operations for conversations
  - Redis persistence with JSON serialization
  - Sorted set indexing for conversation listing
  
- **API Endpoints**
  - `GET /health` - Health check
  - `POST /conversations` - Create conversation
  - `GET /conversations` - List conversations
  - `GET /conversations/{id}` - Get conversation
  - `DELETE /conversations/{id}` - Delete conversation
  - `POST /conversations/{id}/chat` - Chat (streaming/non-streaming)
  
- **Frontend**
  - Web-based chat UI ([index.html](../index.html))
  - Sidebar with conversation list
  - Message streaming display
  - Conversation management (create, delete)
  
- **Documentation**
  - Comprehensive docs/ folder with:
    - README.md - Overview and quick start
    - architecture.md - System design and components
    - api.md - API reference with examples
    - setup.md - Installation and configuration
    - testing.md - Test strategy and procedures
    - glossary.md - Domain terminology
    - roadmap.md - Future plans and milestones
    - changelog.md - This file
  - ADR (Architecture Decision Records) structure
  - Inline code documentation with docstrings
  
- **Configuration**
  - Environment variable support (DIAL_API_KEY, etc.)
  - Docker Compose configuration for infrastructure
  - CORS middleware for local development
  - Redis persistence settings (AOF, LRU eviction)
  
- **Logging**
  - Structured logging with Python logging module
  - Debug-level logs for development
  - Connection and tool call tracking

### Implementation Details

**MCP Servers Connected**:
1. UMS MCP Server (HTTP) - `http://localhost:8005/mcp`
   - Tools: create_user, get_user, search_users, update_user, delete_user
   
2. Fetch MCP Server (HTTP) - `https://remote.mcpservers.org/fetch/mcp`
   - Tools: fetch_url, extract_content
   
3. DuckDuckGo MCP (Docker stdio) - `mcp/duckduckgo:latest`
   - Tools: web_search

**LLM Models Supported**:
- `gpt-4o` (OpenAI via DIAL)
- `claude-3-7-sonnet@20250219` (Anthropic via DIAL)

**Dependencies**:
- `fastapi==0.118.0` - Web framework
- `openai==2.0.0` - DIAL API client
- `fastmcp==2.10.1` - MCP protocol implementation
- `redis[hiredis]==5.0.0` - Redis client with C extension
- `httpx` - HTTP client for MCP connections

### Known Limitations
- No authentication (intentionally skipped for workshop)
- No automated tests (TODO in Milestone 3)
- No PII detection (Additional Task, planned for Milestone 2)
- No production deployment guide (planned for Milestone 2)
- MCP client cleanup not implemented on shutdown
- No retry logic for external service failures
- Global state pattern for ConversationManager (not dependency injection)

### Breaking Changes
- None (initial release)

---

## Development Notes

### Versioning Strategy

This project uses a hybrid versioning approach:

**Workshop Phase**: `Workshop v1.x`
- Focus: Educational value, core functionality
- No production guarantees

**Production Phase**: `v1.x.x` (Semantic Versioning)
- `MAJOR.MINOR.PATCH`
- MAJOR: Breaking API changes
- MINOR: New features, backward-compatible
- PATCH: Bug fixes, backward-compatible

### Release Process (Future)

1. Update CHANGELOG.md with changes
2. Bump version in relevant files
3. Create Git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. Generate release notes from changelog
6. Deploy to staging for validation
7. Deploy to production

### Migration Guide (Future)

When breaking changes are introduced, migration guides will be added here:

**Example**:
```markdown
## Migrating from v1.x to v2.x

### Breaking Changes
- Authentication now required for all endpoints
- Conversation schema includes `user_id` field

### Migration Steps
1. Update API calls to include `Authorization` header
2. Run migration script: `python scripts/migrate_v1_to_v2.py`
3. Restart services
```

---

## Changelog Maintenance

### How to Update

**For each change**, add entry under `[Unreleased]`:

```markdown
### Added
- New feature description

### Changed
- Modified behavior description

### Deprecated
- Feature marked for removal

### Removed
- Deleted feature description

### Fixed
- Bug fix description

### Security
- Security patch description
```

**On release**, move entries from `[Unreleased]` to new version section.

### Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security patches

---

**Next Steps**: Review [Roadmap](./roadmap.md) for planned features or check [README](./README.md) for project overview.
