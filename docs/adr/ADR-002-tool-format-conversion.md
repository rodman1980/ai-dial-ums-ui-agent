# ADR-002: Tool Format Conversion in MCP Clients

## Status
**Accepted** (2025-12-30)

## Context

The project integrates multiple Model Context Protocol (MCP) servers that expose tools in **Anthropic format**:

```json
{
  "name": "search_users",
  "description": "Search for users by criteria",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"}
    }
  }
}
```

However, the DIAL API (and OpenAI API) expects tools in **OpenAI format**:

```json
{
  "type": "function",
  "function": {
    "name": "search_users",
    "description": "Search for users by criteria",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string"}
      }
    }
  }
}
```

**Key differences**:
1. OpenAI wraps in `{type: "function", function: {...}}`
2. Anthropic uses `inputSchema`, OpenAI uses `parameters`
3. Both use JSON Schema internally, but different keys

**Where should conversion happen?**
- Option A: In MCP clients (`get_tools()` method)
- Option B: In `DialClient` before sending to LLM
- Option C: In `ConversationManager` during aggregation
- Option D: Separate converter utility

## Decision

**Perform format conversion in MCP clients' `get_tools()` method.**

```python
# agent/clients/http_mcp_client.py
async def get_tools(self) -> list[dict[str, Any]]:
    tools_result = await self.session.list_tools()
    
    dial_tools = []
    for tool in tools_result.tools:
        dial_tool = {
            "type": "function",  # ← Added wrapper
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema  # ← Renamed key
            }
        }
        dial_tools.append(dial_tool)
    
    return dial_tools
```

## Alternatives Considered

### Alternative 1: Convert in DialClient

```python
# agent/clients/dial_client.py
def __init__(self, tools, ...):
    self.tools = [self._convert_tool(t) for t in tools]

def _convert_tool(self, mcp_tool):
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool["description"],
            "parameters": mcp_tool["inputSchema"]
        }
    }
```

**Rejected because**:
- `DialClient` would need to know about MCP format (leaky abstraction)
- Conversion happens after aggregation (harder to debug per-server issues)
- Assumes all tools need conversion (not true if adding non-MCP tools)

### Alternative 2: Convert in ConversationManager

```python
# agent/conversation_manager.py
def __init__(self, dial_client, redis_client):
    # ... aggregate tools from MCP clients
    converted_tools = [convert_tool(t) for t in all_tools]
    self.dial_client = DialClient(tools=converted_tools, ...)
```

**Rejected because**:
- Mixes concerns (conversation management + format conversion)
- Aggregation logic becomes complex
- Hard to track which tools came from which server

### Alternative 3: Separate Converter Utility

```python
# agent/utils/tool_converter.py
def anthropic_to_openai(tool):
    return {...}

# In MCP client
async def get_tools(self):
    tools = await self.session.list_tools()
    return [anthropic_to_openai(t) for t in tools]
```

**Rejected because**:
- Over-engineering for simple transformation
- Extra file for 5-line conversion
- Harder to discover where conversion happens
- No reuse (each MCP client calls once at startup)

## Consequences

### Positive

✅ **Encapsulation**: MCP clients hide format differences from rest of system  
✅ **Single Responsibility**: Each client handles its own protocol quirks  
✅ **Early Conversion**: Format issues caught at connection time, not during chat  
✅ **Simple Aggregation**: App.py just combines lists without worrying about formats  
✅ **Testable**: Can test conversion independently in client unit tests  
✅ **Extensible**: Easy to add new MCP servers without changing other code

### Negative

❌ **Duplication**: Same conversion code in `HttpMCPClient` and `StdioMCPClient`  
❌ **Hidden Logic**: Not obvious that conversion happens without reading client code  
❌ **Tight Coupling**: Clients know about both MCP and DIAL formats

### Neutral

➖ **Performance**: Negligible (conversion happens once at startup)  
➖ **Memory**: Minimal (tools list is small, typically <10 tools per server)

## Implementation Notes

### Conversion Logic

```python
def _mcp_to_dial_format(mcp_tool) -> dict:
    """Convert MCP (Anthropic) tool to DIAL (OpenAI) format.
    
    Args:
        mcp_tool: Tool object from MCP server (has .name, .description, .inputSchema)
    
    Returns:
        Tool dict in DIAL/OpenAI format
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": mcp_tool.inputSchema
        }
    }
```

### Validation

```python
async def get_tools(self) -> list[dict[str, Any]]:
    tools_result = await self.session.list_tools()
    
    dial_tools = []
    for tool in tools_result.tools:
        dial_tool = self._mcp_to_dial_format(tool)
        
        # Validate structure
        assert "type" in dial_tool, f"Missing 'type' in {tool.name}"
        assert "function" in dial_tool, f"Missing 'function' in {tool.name}"
        assert "name" in dial_tool["function"], f"Missing 'name' in {tool.name}"
        
        dial_tools.append(dial_tool)
    
    logger.info(f"Converted {len(dial_tools)} tools to DIAL format")
    return dial_tools
```

### DRY (Don't Repeat Yourself) Mitigation

If duplication becomes problematic, extract to shared method in base class:

```python
# agent/clients/base_mcp_client.py
class BaseMCPClient:
    @staticmethod
    def mcp_to_dial_format(mcp_tool) -> dict:
        return {
            "type": "function",
            "function": {
                "name": mcp_tool.name,
                "description": mcp_tool.description,
                "parameters": mcp_tool.inputSchema
            }
        }

# In HttpMCPClient and StdioMCPClient
class HttpMCPClient(BaseMCPClient):
    async def get_tools(self):
        tools = await self.session.list_tools()
        return [self.mcp_to_dial_format(t) for t in tools.tools]
```

**Note**: Not implemented yet as duplication is minimal (appears twice, ~5 lines each).

## Related Decisions

- **ADR-001**: Async Factory Pattern - Conversion happens during `create()` initialization
- **ADR-004**: Recursive Tool Calling - `DialClient` receives tools already in correct format

## References

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use](https://docs.anthropic.com/claude/docs/tool-use)
- JSON Schema: [Official Specification](https://json-schema.org/)

## Review Notes

- **2025-12-30**: Initial decision - working well with 3 MCP servers
- **Future**: If adding many more MCP servers, consider base class to reduce duplication
- **Future**: If other tool formats emerge (non-MCP), may need adapter pattern
