# ADR-004: Recursive Tool Calling Pattern

## Status
**Accepted** (2025-12-30)

## Context

Modern LLMs support function calling: they can decide to invoke external tools based on user queries. A single user question may require multiple tool calls:

**Example conversation flow**:
```
User: "Find user John Doe and tell me about his company"
LLM: [calls search_users("John Doe")]
Tool: [returns {id: 42, company: "Acme Corp"}]
LLM: [calls web_search("Acme Corp")]
Tool: [returns company info]
LLM: "John Doe works at Acme Corp, which is..."
```

**Challenge**: How to handle multi-step tool execution?

**Options**:
1. **Recursive pattern**: LLM calls itself after each tool execution
2. **Iterative loop**: While loop checking for tool calls
3. **Single-pass**: Return after first tool call, let caller retry
4. **Queue-based**: Async queue processing tool calls

**Requirements**:
- Support arbitrary tool call depth (user question → tool → LLM → tool → LLM → ...)
- Work with both streaming and non-streaming responses
- Maintain message history correctly
- Prevent infinite loops (rely on LLM to converge)

## Decision

**Implement recursive pattern in `DialClient.response()` and `stream_response()`.**

### Non-Streaming Implementation

```python
async def response(self, messages: list[Message]) -> Message:
    """Execute LLM call with recursive tool calling."""
    # 1. Call LLM
    response = await self.async_openai.chat.completions.create(
        model=self.model,
        messages=[msg.to_dict() for msg in messages],
        tools=self.tools
    )
    
    # 2. Create assistant message
    ai_message = Message(
        role=Role.ASSISTANT,
        content=response.choices[0].message.content
    )
    
    # 3. Check for tool calls
    if response.choices[0].message.tool_calls:
        ai_message.tool_calls = [...]  # Extract tool calls
        
        # 4. Execute tools and append results
        messages.append(ai_message)
        await self._call_tools(ai_message, messages)
        
        # 5. RECURSION: Call LLM again with tool results
        return await self.response(messages)
    
    # 6. Base case: no tool calls, return final answer
    return ai_message
```

### Streaming Implementation

```python
async def stream_response(self, messages: list[Message]) -> AsyncGenerator[str, None]:
    """Stream LLM response with recursive tool calling."""
    stream = await self.async_openai.chat.completions.create(
        model=self.model,
        messages=[msg.to_dict() for msg in messages],
        tools=self.tools,
        stream=True
    )
    
    content_buffer = ""
    tool_deltas = []
    
    # Collect chunks
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield f"data: {json.dumps(chunk_data)}\n\n"
            content_buffer += chunk.choices[0].delta.content
        
        if chunk.choices[0].delta.tool_calls:
            tool_deltas.extend(chunk.choices[0].delta.tool_calls)
    
    # If tool calls detected
    if tool_deltas:
        tool_calls = self._collect_tool_calls(tool_deltas)
        ai_message = Message(role=Role.ASSISTANT, content=content_buffer, tool_calls=tool_calls)
        messages.append(ai_message)
        await self._call_tools(ai_message, messages)
        
        # RECURSION: Stream again with tool results
        async for chunk in self.stream_response(messages):
            yield chunk
        return
    
    # Base case: no tool calls, send completion
    yield "data: [DONE]\n\n"
```

## Alternatives Considered

### Alternative 1: Iterative Loop

```python
async def response(self, messages: list[Message]) -> Message:
    while True:
        response = await self.async_openai.chat.completions.create(...)
        ai_message = ...
        
        if not ai_message.tool_calls:
            return ai_message
        
        messages.append(ai_message)
        await self._call_tools(ai_message, messages)
        # Loop continues
```

**Rejected because**:
- Less readable than recursive pattern
- Streaming version requires complex nested loops
- State management across iterations more error-prone
- Recursion naturally matches call/response structure

### Alternative 2: Single-Pass with Callback

```python
async def response(self, messages, on_tool_call=None):
    response = await self.async_openai.chat.completions.create(...)
    
    if response.tool_calls and on_tool_call:
        await on_tool_call(response.tool_calls, messages)
        # Caller responsible for recursion
```

**Rejected because**:
- Leaks complexity to caller (ConversationManager)
- Caller must know when to stop recursing
- Breaks encapsulation (tool calling is DialClient's responsibility)

### Alternative 3: Queue-Based

```python
async def response(self, messages):
    queue = asyncio.Queue()
    await queue.put(messages)
    
    while not queue.empty():
        msgs = await queue.get()
        response = await self.async_openai.chat.completions.create(...)
        
        if response.tool_calls:
            # Execute tools and re-queue
            await queue.put(updated_messages)
        else:
            return response
```

**Rejected because**:
- Over-engineering for simple sequential process
- No benefit (tool calls are inherently sequential, not parallel)
- Queue adds latency and complexity

## Consequences

### Positive

✅ **Natural Fit**: Matches LLM conversation structure (call → respond → call)  
✅ **Clean Code**: Recursive calls are concise and readable  
✅ **Encapsulation**: Tool calling logic contained in `DialClient`  
✅ **Transparent**: ConversationManager doesn't need to know about recursion  
✅ **Streaming Support**: Pattern works for both streaming and non-streaming  
✅ **Message History**: Automatically maintains correct order (assistant → tool → assistant)

### Negative

❌ **Stack Depth**: Deep recursion (>1000 levels) could hit Python recursion limit  
❌ **Debugging**: Stack traces can be confusing with multiple recursive calls  
❌ **No Max Depth Limit**: Relies on LLM to converge (could theoretically loop forever)  
❌ **Memory**: Each recursive call adds frame to stack  
❌ **Testing**: Harder to test edge cases (deep recursion scenarios)

### Neutral

➖ **Performance**: Negligible overhead from recursion (network latency dominates)  
➖ **Convergence**: LLMs typically converge within 1-5 tool call cycles

## Implementation Notes

### Recursion Depth Analysis

**Typical depths**:
- Simple query (no tools): 0 recursion levels
- Single tool call: 1 recursion level
- Multi-step reasoning: 2-3 recursion levels
- Complex workflows: 3-5 recursion levels

**Python recursion limit**:
```python
import sys
sys.getrecursionlimit()  # Default: 1000
```

**Risk assessment**: Extremely low. Hitting 1000 levels would require user asking question that triggers 1000 sequential tool calls, which is unrealistic (and would timeout/cost too much).

### Adding Max Depth Protection (Future)

If needed, add depth counter:

```python
async def response(self, messages: list[Message], _depth: int = 0) -> Message:
    MAX_RECURSION_DEPTH = 10  # Safety limit
    
    if _depth >= MAX_RECURSION_DEPTH:
        logger.error(f"Max recursion depth {MAX_RECURSION_DEPTH} reached")
        return Message(
            role=Role.ASSISTANT,
            content="Sorry, this query requires too many steps."
        )
    
    # ... normal logic ...
    
    if ai_message.tool_calls:
        messages.append(ai_message)
        await self._call_tools(ai_message, messages)
        return await self.response(messages, _depth + 1)  # Increment depth
```

### Tool Execution Logic

```python
async def _call_tools(self, ai_message: Message, messages: list[Message]):
    """Execute all tool calls and append results to messages."""
    for tool_call in ai_message.tool_calls:
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])
        
        # Route to correct MCP client
        mcp_client = self.tool_name_client_map[tool_name]
        
        # Execute tool
        result = await mcp_client.call_tool(tool_name, tool_args)
        
        # Append tool result message
        messages.append(Message(
            role=Role.TOOL,
            content=str(result),
            tool_call_id=tool_call["id"],
            name=tool_name
        ))
```

### Debugging Recursive Calls

```python
logger.debug(f"DialClient.response() called with {len(messages)} messages")

if ai_message.tool_calls:
    logger.debug(f"Tool calls: {[tc['function']['name'] for tc in ai_message.tool_calls]}")
    logger.debug(f"Recursing into response() with {len(messages)} messages")
```

**Log example**:
```
DEBUG: DialClient.response() called with 2 messages
DEBUG: Tool calls: ['search_users']
DEBUG: Executing tool: search_users
DEBUG: Recursing into response() with 4 messages
DEBUG: DialClient.response() called with 4 messages
DEBUG: No tool calls, returning final answer
```

## Related Decisions

- **ADR-002**: Tool Format Conversion - Tools passed to LLM are in correct format
- **ADR-005**: Global State Pattern - ConversationManager delegates to DialClient's recursive logic

## References

- [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use Documentation](https://docs.anthropic.com/claude/docs/tool-use)
- [Python Recursion Limit](https://docs.python.org/3/library/sys.html#sys.getrecursionlimit)
- [Tail Call Optimization](https://en.wikipedia.org/wiki/Tail_call) (Note: Python doesn't support TCO)

## Review Notes

- **2025-12-30**: Initial decision - working well in practice
- **Future**: Monitor recursion depths in production logs
- **Future**: If deep recursion becomes issue, consider iterative loop or max depth limit
- **Future**: Could parallelize independent tool calls (requires dependency analysis)
