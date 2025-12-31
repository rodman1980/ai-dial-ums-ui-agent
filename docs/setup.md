---
title: Setup Guide
description: Complete environment setup, dependency installation, configuration, and deployment instructions
version: 1.0.0
last_updated: 2025-12-30
related: [README.md, architecture.md, testing.md]
tags: [setup, installation, configuration, deployment]
---

# Setup Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Development Workflow](#development-workflow)

## Prerequisites

### System Requirements

| Requirement | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Core runtime |
| **Docker** | 20.10+ | MCP server containers |
| **Docker Compose** | 2.0+ | Infrastructure orchestration |
| **Git** | 2.30+ | Source control |
| **EPAM VPN** | - | DIAL API access |

### Platform-Specific Notes

**macOS**:
```bash
# Install Docker Desktop
brew install --cask docker

# Verify installation
docker --version
docker-compose --version
```

**Linux**:
```bash
# Install Docker Engine
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Windows**:
- Install Docker Desktop for Windows
- Enable WSL2 backend (recommended)
- Install Python from python.org or Microsoft Store

### Network Requirements

- **EPAM VPN**: Required for DIAL API access (`https://ai-proxy.lab.epam.com`)
- **Outbound HTTP/HTTPS**: For remote Fetch MCP server
- **Docker Hub**: To pull `mcp/duckduckgo:latest` image

### API Keys

1. **DIAL API Key**:
   - Obtain from DIAL platform administrator
   - Required for LLM inference
   - Store in environment variable (never commit to Git)

## Installation

### 1. Clone Repository

```bash
git clone https://git.epam.com/ai-dial-ums-ui-agent.git
cd ai-dial-ums-ui-agent
```

### 2. Create Virtual Environment

**Using venv (recommended)**:
```bash
python3 -m venv dial_ums
source dial_ums/bin/activate  # macOS/Linux
# OR
dial_ums\Scripts\activate  # Windows
```

**Using conda**:
```bash
conda create -n dial_ums python=3.11
conda activate dial_ums
```

**Verify activation**:
```bash
which python  # Should point to venv/conda path
python --version  # Should be 3.11+
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected packages** ([requirements.txt](../requirements.txt)):
- `httpx` - HTTP client for MCP connections
- `openai==2.0.0` - DIAL API client
- `fastmcp==2.10.1` - MCP protocol implementation
- `redis[hiredis]==5.0.0` - Redis client with C extension
- `fastapi==0.118.0` - Web framework

**Verify installation**:
```bash
pip list | grep -E "httpx|openai|fastmcp|redis|fastapi"
```

### 4. Pull Docker Images

```bash
# DuckDuckGo MCP server (stdio-based)
docker pull mcp/duckduckgo:latest

# Verify image
docker images | grep duckduckgo
```

### 5. Start Infrastructure Services

```bash
docker-compose up -d
```

**Services started** ([docker-compose.yml](../docker-compose.yml)):
- `userservice` - Mock UMS API (port 8041)
- `ums-mcp-server` - MCP interface to UMS (port 8005)
- `redis-ums` - Conversation persistence (port 6379)
- `redis-insight` - Redis GUI (port 6380)

**Verify services**:
```bash
docker-compose ps

# Expected output:
# NAME                IMAGE                              STATUS    PORTS
# userservice         khshanovskyi/mockuserservice       Up        0.0.0.0:8041->8000/tcp
# ums-mcp-server      khshanovskyi/ums-mcp-server        Up        0.0.0.0:8005->8005/tcp
# redis-ums           redis:7.2.4-alpine3.19            Up        0.0.0.0:6379->6379/tcp
# redis-insight       redislabs/redisinsight            Up        0.0.0.0:6380->5540/tcp
```

**Health checks**:
```bash
# UMS Service
curl http://localhost:8041/health

# UMS MCP Server
curl http://localhost:8005/health

# Redis
redis-cli ping  # Should return "PONG"
```

## Configuration

### Environment Variables

Create `.env` file in project root (DO NOT commit):

```bash
# DIAL API Configuration
DIAL_API_KEY=your-dial-api-key-here
DIAL_ENDPOINT=https://ai-proxy.lab.epam.com
DIAL_MODEL=gpt-4o  # or claude-3-7-sonnet@20250219

# MCP Server URLs (defaults in code)
UMS_MCP_URL=http://localhost:8005/mcp
FETCH_MCP_URL=https://remote.mcpservers.org/fetch/mcp

# Redis Configuration (defaults in code)
REDIS_HOST=localhost
REDIS_PORT=6379

# Application Configuration
APP_HOST=0.0.0.0
APP_PORT=8011
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

**Load environment**:
```bash
# Using export (bash/zsh)
export DIAL_API_KEY="your-key"

# Using .env file (requires python-dotenv)
pip install python-dotenv
# Then add to app.py:
# from dotenv import load_dotenv
# load_dotenv()
```

### Redis Configuration

**Default settings** ([docker-compose.yml](../docker-compose.yml)):
```yaml
maxmemory: 2000mb
maxmemory-policy: allkeys-lru  # Evict least recently used
save: 60 1, 300 10, 900 100    # Persistence snapshots
appendonly: yes                 # AOF persistence
```

**Connect via Redis Insight**:
1. Open `http://localhost:6380`
2. Add database: `redis-ums:6379` (use Docker network hostname)
3. Browse keys with pattern `conversation:*`

### Docker Compose Overrides

**Custom configuration** (`docker-compose.override.yml`):
```yaml
version: '3.8'

services:
  ums-mcp-server:
    environment:
      - LOG_LEVEL=DEBUG
  
  redis-ums:
    volumes:
      - ./redis-custom.conf:/usr/local/etc/redis/redis.conf
```

Apply overrides:
```bash
docker-compose up -d
```

## Running the Application

### Development Mode

**Method 1: Direct Python**:
```bash
# Ensure venv activated
source dial_ums/bin/activate

# Run application
python -m agent.app

# Expected output:
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# INFO:     Application startup initiated
# INFO:     Connected to MCP server: http://localhost:8005/mcp
# INFO:     Connected to MCP server: https://remote.mcpservers.org/fetch/mcp
# INFO:     Connected to MCP server via Docker: mcp/duckduckgo:latest
# INFO:     Redis connection successful
# INFO:     Application startup complete
# INFO:     Uvicorn running on http://0.0.0.0:8011
```

**Method 2: Uvicorn with reload**:
```bash
uvicorn agent.app:app --host 0.0.0.0 --port 8011 --reload

# Auto-reloads on file changes (useful for development)
```

**Method 3: Make/script**:
```bash
# Create run.sh
#!/bin/bash
source dial_ums/bin/activate
export DIAL_API_KEY="your-key"
python -m agent.app

chmod +x run.sh
./run.sh
```

### Access Points

Once running, access:

| Service | URL | Purpose |
|---------|-----|---------|
| **API Docs** | `http://localhost:8011/docs` | Swagger UI |
| **ReDoc** | `http://localhost:8011/redoc` | Alternative API docs |
| **Health Check** | `http://localhost:8011/health` | Status verification |
| **Chat UI** | `file:///path/to/index.html` | Open directly in browser |
| **Redis Insight** | `http://localhost:6380` | Database inspection |
| **UMS Service** | `http://localhost:8041` | Mock user API |

### Frontend Setup

**No build step required** - `index.html` is pure HTML/CSS/JavaScript.

1. Locate [index.html](../index.html) in project root
2. Open in modern browser (Chrome, Firefox, Safari, Edge)
3. Browser must support:
   - Fetch API
   - EventSource (SSE)
   - ES6+ JavaScript

**CORS Note**: Since HTML is opened via `file://` protocol, FastAPI must allow all origins (already configured in [app.py](../agent/app.py)).

## Verification

### Quick Verification Checklist

```bash
# 1. Check Docker services
docker-compose ps | grep -E "Up|healthy"

# 2. Verify Redis
redis-cli ping

# 3. Test UMS MCP
curl http://localhost:8005/health

# 4. Check FastAPI
curl http://localhost:8011/health

# 5. Test conversation creation
curl -X POST http://localhost:8011/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "Test"}'

# Expected: {"id": "...", "title": "Test", ...}
```

### Comprehensive Tests

#### 1. Health Endpoints

```bash
# FastAPI health
curl http://localhost:8011/health
# Expected: {"status": "healthy", "conversation_manager_initialized": true}

# UMS Service health
curl http://localhost:8041/health
# Expected: {"status": "healthy"}

# UMS MCP Server health
curl http://localhost:8005/health
# Expected: {"status": "healthy"}
```

#### 2. Conversation CRUD

```bash
# Create conversation
CONV_ID=$(curl -s -X POST http://localhost:8011/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "Verification Test"}' | jq -r '.id')

echo "Created: $CONV_ID"

# List conversations
curl -s http://localhost:8011/conversations | jq

# Get specific conversation
curl -s http://localhost:8011/conversations/$CONV_ID | jq

# Delete conversation
curl -s -X DELETE http://localhost:8011/conversations/$CONV_ID
```

#### 3. Chat Interaction (Non-Streaming)

```bash
# Create conversation
CONV_ID=$(curl -s -X POST http://localhost:8011/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "Chat Test"}' | jq -r '.id')

# Send message
curl -s -X POST http://localhost:8011/conversations/$CONV_ID/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"role": "user", "content": "Hello"},
    "stream": false
  }' | jq
```

#### 4. Streaming Test

```bash
curl -N -X POST http://localhost:8011/conversations/$CONV_ID/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"role": "user", "content": "What is MCP?"},
    "stream": true
  }'

# Expected: SSE stream ending with "data: [DONE]"
```

#### 5. Tool Calling Test

```bash
# Test UMS tool calling
curl -s -X POST http://localhost:8011/conversations/$CONV_ID/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"role": "user", "content": "Show me all users"},
    "stream": false
  }' | jq '.content'

# Should invoke search_users tool and return results
```

#### 6. Redis Verification

```bash
# Connect to Redis
redis-cli

# List all conversation keys
KEYS conversation:*

# Get conversation data
GET conversation:<uuid>

# Check sorted set
ZRANGE conversations:list 0 -1 WITHSCORES
```

## Troubleshooting

### Common Issues

#### 1. "DIAL_API_KEY not set"

**Symptoms**: Error on startup or when sending chat messages.

**Solution**:
```bash
export DIAL_API_KEY="your-key-here"

# Or add to ~/.bashrc / ~/.zshrc
echo 'export DIAL_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

#### 2. "Redis connection refused"

**Symptoms**: `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379`

**Solution**:
```bash
# Check if Redis is running
docker-compose ps redis-ums

# Restart if needed
docker-compose restart redis-ums

# Check logs
docker-compose logs redis-ums
```

#### 3. "Docker image not found: mcp/duckduckgo:latest"

**Symptoms**: `StdioMCPClient` fails to connect.

**Solution**:
```bash
docker pull mcp/duckduckgo:latest
docker images | grep duckduckgo
```

#### 4. CORS errors in browser

**Symptoms**: Console shows `CORS policy: No 'Access-Control-Allow-Origin' header`

**Solution**:
- Verify CORS middleware in [app.py](../agent/app.py)
- Ensure `allow_origins=["*"]` is set
- Clear browser cache
- Try different browser

#### 5. "Conversation manager not initialized"

**Symptoms**: `/health` returns `conversation_manager_initialized: false`

**Solution**:
```bash
# Check application logs for startup errors
tail -f logs/app.log  # if logging to file

# Common causes:
# - MCP server unreachable
# - Redis connection failed
# - Missing DIAL_API_KEY

# Restart with verbose logging
LOG_LEVEL=DEBUG python -m agent.app
```

#### 6. Port already in use

**Symptoms**: `OSError: [Errno 48] Address already in use`

**Solution**:
```bash
# Find process using port
lsof -i :8011  # macOS/Linux
netstat -ano | findstr :8011  # Windows

# Kill process or change port
export APP_PORT=8012
python -m agent.app
```

#### 7. VPN connection required

**Symptoms**: `ConnectionError` when calling DIAL API.

**Solution**:
- Connect to EPAM VPN
- Test connectivity: `curl -I https://ai-proxy.lab.epam.com`
- Verify VPN split tunneling doesn't block internal routes

### Debugging Tools

#### Logs

```bash
# Application logs (stdout by default)
python -m agent.app 2>&1 | tee logs/app.log

# Docker Compose logs
docker-compose logs -f

# Specific service logs
docker-compose logs -f ums-mcp-server
```

#### Redis Inspection

```bash
# CLI
redis-cli
> MONITOR  # Watch all commands in real-time
> INFO     # Server stats
> KEYS *   # List all keys (careful in production!)

# Redis Insight (GUI)
# Open http://localhost:6380
# Add database: redis-ums:6379
# Browse keys, monitor commands, view memory usage
```

#### Network Debugging

```bash
# Test MCP server connectivity
curl -v http://localhost:8005/health
curl -v https://remote.mcpservers.org/fetch/mcp

# Test DIAL API (requires VPN)
curl -H "Authorization: Bearer $DIAL_API_KEY" \
  https://ai-proxy.lab.epam.com/v1/models

# Docker network inspection
docker network inspect ai-dial-ums-ui-agent_default
```

#### Python Debugging

**Interactive shell**:
```python
python
>>> from agent.clients.http_mcp_client import HttpMCPClient
>>> import asyncio
>>> client = asyncio.run(HttpMCPClient.create("http://localhost:8005/mcp"))
>>> tools = asyncio.run(client.get_tools())
>>> print(tools)
```

**Debugger** (pdb):
```python
# Add to code
import pdb; pdb.set_trace()

# Run
python -m agent.app
```

### Performance Issues

#### Slow Startup

**Check**:
- MCP server connection timeouts
- Docker image pulls
- Redis connection latency

**Solution**:
```bash
# Pre-pull images
docker-compose pull

# Start services early
docker-compose up -d
sleep 10  # Wait for health checks

# Then start app
python -m agent.app
```

#### Slow Responses

**Check**:
- LLM inference time (typical: 2-10s)
- Tool execution latency
- Redis query time

**Monitoring**:
```bash
# Add timing logs to code
import time
start = time.time()
# ... operation ...
logger.info(f"Operation took {time.time() - start:.2f}s")
```

## Development Workflow

### Daily Workflow

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Activate venv
source dial_ums/bin/activate

# 3. Set environment
export DIAL_API_KEY="your-key"

# 4. Run with auto-reload
uvicorn agent.app:app --reload

# 5. Develop & test in browser (index.html)

# 6. Commit changes
git add .
git commit -m "Your changes"
git push
```

### Testing Changes

```bash
# Unit tests (TODO: add tests)
pytest tests/

# Manual API testing
curl http://localhost:8011/health

# Frontend testing
# Open index.html in browser
# Check browser console for errors
```

### Stopping Services

```bash
# Stop FastAPI
Ctrl+C

# Stop Docker services
docker-compose down

# Stop and remove volumes (clears Redis data)
docker-compose down -v
```

### Clean Reinstall

```bash
# Remove venv
rm -rf dial_ums/

# Stop and remove containers
docker-compose down -v

# Remove Docker images
docker rmi khshanovskyi/mockuserservice
docker rmi khshanovskyi/ums-mcp-server
docker rmi mcp/duckduckgo:latest

# Start fresh installation
# ... follow Installation section ...
```

---

**Next Steps**: Proceed to [Testing Guide](./testing.md) to validate your installation, or refer to [API Reference](./api.md) for endpoint details.
