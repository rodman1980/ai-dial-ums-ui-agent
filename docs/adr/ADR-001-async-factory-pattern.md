# ADR-001: Async Factory Pattern for MCP Clients

## Status
**Accepted** (2025-12-30)

## Context

MCP client initialization requires establishing network connections (HTTP/SSE or Docker stdio), which are inherently asynchronous operations in Python. However, Python's `__init__()` method cannot be `async`, creating a chicken-and-egg problem:

- Need to establish connection before client is usable
- Connection requires async/await
- Constructor cannot await

**Problematic pattern** (doesn't work):
```python
class HttpMCPClient:
    def __init__(self, url):
        self.session = await self.connect()  # ❌ SyntaxError: can't use await in __init__
```

**Workarounds considered**:
1. Sync init + explicit `await connect()` call (error-prone, client usable before connected)
2. Threading (blocks async event loop, defeats purpose of async)
3. Lazy initialization (complex state management, hidden behavior)
4. Async factory method (clear pattern, explicit)

## Decision

**Use async factory class method pattern** for MCP client initialization:

```python
class HttpMCPClient:
    def __init__(self, url):
        self.url = url
        self.session = None  # Not connected yet
    
    @classmethod
    async def create(cls, url):
        """Factory method: creates AND connects client."""
        instance = cls(url)
        await instance.connect()
        return instance
    
    async def connect(self):
        """Private: establish connection."""
        # async connection logic
        self.session = ...
```

**Usage**:
```python
# ✅ Correct: fully connected client
client = await HttpMCPClient.create("http://localhost:8005/mcp")

# ❌ Incorrect: unconnected client (session is None)
client = HttpMCPClient("http://localhost:8005/mcp")
```

## Alternatives Considered

### Alternative 1: Sync Init + Manual Connect

```python
client = HttpMCPClient(url)  # Not connected
await client.connect()       # Must remember to call
```

**Rejected because**:
- Error-prone: easy to forget `connect()` call
- Client is in invalid state between init and connect
- Hard to enforce connection requirement

### Alternative 2: Lazy Initialization

```python
class HttpMCPClient:
    async def get_tools(self):
        if not self.session:
            await self.connect()
        # use session
```

**Rejected because**:
- Hidden behavior (connection happens implicitly)
- Every method needs connection check
- Complex error handling (when does connection fail?)
- Poor developer experience (unexpected delays)

### Alternative 3: Separate Factory Class

```python
class MCPClientFactory:
    @staticmethod
    async def create_http_client(url):
        # initialization logic
```

**Rejected because**:
- Additional class for simple pattern
- Separates factory from client (discoverability)
- No access to `cls` for inheritance

## Consequences

### Positive

✅ **Clear semantics**: `create()` name signals that object is being constructed  
✅ **Always valid**: Returned client is guaranteed to be connected  
✅ **Explicit async**: `await` requirement makes async nature visible  
✅ **Type-safe**: Returns correct class type, works with type hints  
✅ **Testable**: Easy to mock `create()` method  
✅ **Inheritance-friendly**: Subclasses can override `create()` or `connect()`

### Negative

❌ **Discipline required**: Developers must use `create()`, not `__init__()`  
❌ **Documentation burden**: Must clearly explain pattern in docstrings  
❌ **Linting challenges**: Static analyzers may flag unused `__init__`  
❌ **Non-standard**: Not a built-in Python pattern (though common in async codebases)

### Neutral

➖ **Two ways to instantiate**: Direct `__init__()` still possible but wrong  
➖ **Pattern complexity**: Adds one more concept to understand  

## Implementation Notes

### Pattern Template

```python
class AsyncResource:
    """Resource requiring async initialization.
    
    Use create() factory method, not __init__() directly.
    """
    
    def __init__(self, config):
        """Private constructor. Use create() instead."""
        self.config = config
        self.resource = None
    
    @classmethod
    async def create(cls, config):
        """Create and initialize resource (async factory).
        
        Returns:
            Fully initialized AsyncResource instance.
        """
        instance = cls(config)
        await instance._initialize()
        return instance
    
    async def _initialize(self):
        """Initialize async resources."""
        self.resource = await some_async_operation()
```

### Error Handling

```python
@classmethod
async def create(cls, url):
    """Create client or raise on connection failure."""
    instance = cls(url)
    try:
        await instance.connect()
    except Exception as e:
        logger.error(f"Failed to connect to {url}: {e}")
        raise  # Let caller handle connection errors
    return instance
```

### Testing

```python
@pytest.mark.asyncio
async def test_create_client():
    """Test async factory pattern."""
    client = await HttpMCPClient.create("http://test")
    assert client.session is not None  # Guaranteed connected
    
    tools = await client.get_tools()  # No additional setup needed
    assert len(tools) > 0
```

## Related Decisions

- **ADR-002**: Tool Format Conversion - `create()` is where format conversion happens during initialization
- **Architecture**: All MCP clients follow this pattern for consistency

## References

- Python asyncio documentation: [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
- Real Python: [Async IO in Python](https://realpython.com/async-io-python/)
- Stack Overflow: [Async __init__ workarounds](https://stackoverflow.com/questions/33128325/how-to-set-class-attribute-with-await-in-init)

## Review Notes

- **2025-12-30**: Initial decision - pattern working well in `HttpMCPClient` and `StdioMCPClient`
- **Future**: Consider adding `__new__()` override to prevent direct instantiation
