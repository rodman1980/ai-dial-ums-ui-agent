# ADR-005: Global ConversationManager State

## Status
**Accepted** (2025-12-30)

## Context

FastAPI endpoints need access to `ConversationManager` instance to handle chat requests. The `ConversationManager` requires:
- Initialized `DialClient` (with aggregated MCP tools)
- Connected Redis client
- All MCP clients initialized

These components are created during application startup (in `lifespan()` context manager). How should endpoints access the initialized `ConversationManager`?

**Options**:
1. **Global variable** set during startup
2. **Dependency Injection** via FastAPI's `Depends()`
3. **Application state** (`app.state.conversation_manager`)
4. **Singleton pattern** with lazy initialization
5. **Context variables** (`contextvars` module)

**Requirements**:
- Initialized once at startup
- Accessible from all endpoints
- No re-initialization on each request
- Simple to use in endpoint functions

## Decision

**Use global variable set during `lifespan()` startup.**

```python
# agent/app.py
from agent.conversation_manager import ConversationManager

# Global state: initialized during lifespan
conversation_manager: Optional[ConversationManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global conversation_manager
    
    # Initialize all clients
    dial_client = DialClient(...)
    redis_client = redis.Redis(...)
    
    # Create ConversationManager
    conversation_manager = ConversationManager(dial_client, redis_client)
    
    yield  # Application runs
    
    # Cleanup (TODO)


app = FastAPI(lifespan=lifespan)


@app.post("/conversations/{conversation_id}/chat")
async def chat(conversation_id: str, request: ChatRequest):
    if not conversation_manager:
        raise HTTPException(500, "Manager not initialized")
    
    # Use global conversation_manager
    return await conversation_manager.chat(...)
```

## Alternatives Considered

### Alternative 1: Dependency Injection

```python
async def get_conversation_manager() -> ConversationManager:
    """Dependency that returns conversation_manager."""
    if not conversation_manager:
        raise HTTPException(500, "Manager not initialized")
    return conversation_manager


@app.post("/chat")
async def chat(
    manager: ConversationManager = Depends(get_conversation_manager)
):
    return await manager.chat(...)
```

**Rejected because**:
- More boilerplate (dependency function + Depends() in every endpoint)
- No actual dependency injection (still uses global variable)
- Doesn't improve testability (need to mock global anyway)
- Adds complexity without benefit (we're not swapping implementations)

### Alternative 2: Application State

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    dial_client = DialClient(...)
    redis_client = redis.Redis(...)
    
    app.state.conversation_manager = ConversationManager(
        dial_client, redis_client
    )
    
    yield


@app.post("/chat")
async def chat(request: Request):
    manager = request.app.state.conversation_manager
    return await manager.chat(...)
```

**Rejected because**:
- Requires `Request` parameter in every endpoint (noisy)
- More typing: `request.app.state.conversation_manager` vs `conversation_manager`
- No testability advantage (still need to set state in tests)
- `app.state` is essentially a global namespace

### Alternative 3: Singleton Pattern

```python
class ConversationManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("Not initialized")
        return cls._instance
    
    @classmethod
    def initialize(cls, dial_client, redis_client):
        cls._instance = cls(dial_client, redis_client)


@app.post("/chat")
async def chat(...):
    manager = ConversationManager.get_instance()
```

**Rejected because**:
- More complex than simple global variable
- Hidden state (harder to understand initialization flow)
- Testing requires singleton reset between tests
- Overkill for single-instance scenario

### Alternative 4: Context Variables

```python
from contextvars import ContextVar

conversation_manager_var: ContextVar[ConversationManager] = ContextVar('manager')


@app.post("/chat")
async def chat(...):
    manager = conversation_manager_var.get()
```

**Rejected because**:
- Context variables designed for request-scoped data, not app-level singletons
- More complex than needed
- Doesn't solve the initialization problem

## Consequences

### Positive

✅ **Simple**: Most straightforward approach, minimal code  
✅ **Explicit**: `global conversation_manager` clearly indicates global state  
✅ **Fast**: No indirection, direct variable access  
✅ **Readable**: Obvious where instance comes from  
✅ **Type Hints**: Works well with type checkers (`Optional[ConversationManager]`)  
✅ **Debugging**: Easy to inspect in debugger

### Negative

❌ **Global State**: Generally considered anti-pattern in OOP  
❌ **Testing**: Requires setting global in test fixtures  
❌ **Thread Safety**: Not thread-safe (but FastAPI uses async, not threads)  
❌ **Import Side Effects**: Importing module creates global variable  
❌ **Harder to Mock**: Need to patch module-level global

### Neutral

➖ **Single Instance**: Pattern enforces singleton (which is desired here)  
➖ **Initialization Order**: Must ensure startup runs before endpoints called

## Implementation Notes

### Proper Initialization Check

```python
@app.post("/conversations/{id}/chat")
async def chat(id: str, request: ChatRequest):
    if not conversation_manager:
        raise HTTPException(
            status_code=500,
            detail="Conversation manager not initialized"
        )
    
    # Safe to use conversation_manager here
    return await conversation_manager.chat(...)
```

### Type Hints

```python
from typing import Optional

conversation_manager: Optional[ConversationManager] = None
```

**Why Optional?**
- Indicates it's None initially
- Type checker warns if used without None check
- Documents initialization pattern

### Testing Pattern

```python
# tests/conftest.py
import pytest
from agent import app

@pytest.fixture
async def mock_conversation_manager(mocker):
    """Mock global conversation_manager."""
    mock_manager = mocker.AsyncMock(spec=ConversationManager)
    
    # Patch global
    with mocker.patch("agent.app.conversation_manager", mock_manager):
        yield mock_manager


# tests/test_endpoints.py
async def test_chat_endpoint(client, mock_conversation_manager):
    response = await client.post("/conversations/123/chat", ...)
    
    # Verify manager was called
    mock_conversation_manager.chat.assert_called_once()
```

### Alternative Testing: Use TestClient

```python
from fastapi.testclient import TestClient
from agent.app import app, conversation_manager

def test_chat():
    # Initialize conversation_manager for test
    app.dependency_overrides[conversation_manager] = mock_manager
    
    with TestClient(app) as client:
        response = client.post("/chat", ...)
```

### Cleanup (Future TODO)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global conversation_manager
    
    # Startup
    conversation_manager = ConversationManager(...)
    
    yield
    
    # Shutdown: cleanup connections
    if conversation_manager:
        await conversation_manager.dial_client.close()
        await conversation_manager.redis.close()
        conversation_manager = None
```

## When to Reconsider This Decision

**Migrate away from global state if**:
- Adding multi-tenancy (different managers per tenant)
- Implementing hot-reload with config changes
- Switching to multi-process deployment (need process-safe state)
- Test complexity becomes unmanageable
- Adding multiple FastAPI apps in same process

**Migration path**:
Use FastAPI dependency injection:

```python
async def get_manager(request: Request) -> ConversationManager:
    return request.app.state.conversation_manager

@app.post("/chat")
async def chat(manager: Annotated[ConversationManager, Depends(get_manager)]):
    return await manager.chat(...)
```

## Related Decisions

- **ADR-001**: Async Factory Pattern - Clients created in lifespan set global manager
- **ADR-003**: Redis JSON Serialization - Manager uses Redis for persistence
- **ADR-004**: Recursive Tool Calling - Manager delegates to DialClient's recursive logic

## References

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Python Global Variables](https://docs.python.org/3/faq/programming.html#what-are-the-rules-for-local-and-global-variables)
- [Dependency Injection Principle](https://en.wikipedia.org/wiki/Dependency_injection)

## Review Notes

- **2025-12-30**: Initial decision - simplicity prioritized for workshop project
- **Future**: If testability becomes major issue, migrate to proper DI
- **Future**: If adding multi-tenancy, will need per-tenant managers (requires DI)
- **Production**: Consider DI pattern for better separation of concerns
