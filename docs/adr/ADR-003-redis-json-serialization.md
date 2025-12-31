# ADR-003: Redis JSON Serialization for Conversation Storage

## Status
**Accepted** (2025-12-30)

## Context

Conversations must be persisted to survive application restarts. Each conversation contains:
- Metadata: `id`, `title`, `created_at`, `updated_at`
- Message history: Array of Message objects with varying structure

**Message complexity**:
```python
Message(
    role=Role.ASSISTANT,
    content="Answer",
    tool_calls=[{
        "id": "call_123",
        "type": "function",
        "function": {"name": "search_users", "arguments": "{}"}
    }]
)
```

**Storage options**:
1. Redis String with JSON serialization
2. Redis Hash (flat key-value)
3. Redis JSON module (RedisJSON)
4. External database (PostgreSQL, MongoDB)

**Requirements**:
- Store nested message arrays
- Preserve message order
- Support arbitrary message fields
- Fast read/write operations
- Simple deployment (workshop project)

## Decision

**Store conversations as JSON strings in Redis String values.**

```python
# Serialization
conversation_data = {
    "id": str(uuid.uuid4()),
    "title": "Chat Title",
    "messages": [msg.model_dump() for msg in messages],
    "created_at": datetime.now(UTC).isoformat(),
    "updated_at": datetime.now(UTC).isoformat()
}

await redis.set(
    f"conversation:{conversation_id}",
    json.dumps(conversation_data)
)

# Deserialization
json_str = await redis.get(f"conversation:{conversation_id}")
conversation = json.loads(json_str)
messages = [Message(**msg) for msg in conversation["messages"]]
```

**Additional indexing** via sorted set:
```python
await redis.zadd(
    "conversations:list",
    {conversation_id: datetime.now(UTC).timestamp()}
)
```

## Alternatives Considered

### Alternative 1: Redis Hash

```python
await redis.hset(
    f"conversation:{id}",
    mapping={
        "id": id,
        "title": title,
        "messages": json.dumps(messages),  # Still need JSON for array
        "created_at": created_at
    }
)
```

**Rejected because**:
- Messages still require JSON (Hash doesn't support nested arrays)
- No benefit over String (complexity increases, no payload reduction)
- Harder to retrieve full conversation (need HGETALL + parse messages)
- Field-level updates not needed (conversations updated atomically)

### Alternative 2: Redis JSON Module (RedisJSON)

```python
await redis_json.set(
    f"conversation:{id}",
    "$",
    conversation_data
)

# Supports JSON path queries
messages = await redis_json.get(f"conversation:{id}", "$.messages")
```

**Rejected because**:
- Additional Redis module installation required
- Not available in standard Redis Docker image
- Over-engineering for simple read/write pattern
- Querying capabilities unused (always fetch full conversation)
- Adds deployment complexity (workshop constraint)

### Alternative 3: PostgreSQL with JSONB

```python
await db.execute(
    "INSERT INTO conversations (id, data) VALUES ($1, $2)",
    id, json.dumps(conversation_data)
)
```

**Rejected because**:
- Requires separate database service
- Overkill for simple key-value storage
- Adds dependency and complexity
- Redis already required for other features (future caching, sessions)
- No relational queries needed

### Alternative 4: MongoDB

```python
await mongo.conversations.insert_one(conversation_data)
```

**Rejected because**:
- Another database to manage
- Schema flexibility not needed (structure is fixed)
- No complex queries required
- Redis sufficient and already in stack

## Consequences

### Positive

✅ **Simple**: Standard Redis String operations (`SET`, `GET`, `DELETE`)  
✅ **Fast**: O(1) read/write operations  
✅ **Minimal Dependencies**: Uses standard Redis, no modules  
✅ **Easy Debugging**: Can inspect JSON with `redis-cli GET conversation:{id}`  
✅ **Portable**: JSON is universal, easy to migrate to other storage  
✅ **Atomic**: Full conversation read/write in single operation  
✅ **Type-Safe**: Pydantic serialization/deserialization via `model_dump()`

### Negative

❌ **No Partial Updates**: Must read, modify, write entire conversation  
❌ **Network Overhead**: Fetching large conversations sends all messages  
❌ **No Field Indexing**: Can't query by message content or role  
❌ **Memory Usage**: Full JSON string loaded into memory on read  
❌ **Serialization Cost**: JSON encode/decode on every operation

### Neutral

➖ **Scalability**: Fine for thousands of conversations, may need optimization for millions  
➖ **Message Limits**: No enforcement of max messages per conversation  
➖ **Compression**: Could gzip JSON if size becomes issue (not implemented)

## Implementation Notes

### Serialization Pattern

```python
def _conversation_to_json(conversation: dict) -> str:
    """Serialize conversation to JSON string.
    
    Handles:
    - Message objects → dicts via model_dump()
    - Datetime objects → ISO 8601 strings
    """
    serializable = {
        "id": conversation["id"],
        "title": conversation["title"],
        "messages": [msg.model_dump() for msg in conversation["messages"]],
        "created_at": conversation["created_at"],
        "updated_at": conversation["updated_at"]
    }
    return json.dumps(serializable)

def _json_to_conversation(json_str: str) -> dict:
    """Deserialize JSON string to conversation dict.
    
    Reconstructs:
    - Message dicts → Message objects
    - ISO 8601 strings → datetime objects (if needed)
    """
    data = json.loads(json_str)
    data["messages"] = [Message(**msg) for msg in data["messages"]]
    return data
```

### Error Handling

```python
async def get_conversation(conversation_id: str) -> Optional[dict]:
    try:
        json_str = await self.redis.get(f"conversation:{conversation_id}")
        if not json_str:
            return None
        
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupt conversation data for {conversation_id}: {e}")
        return None
    except redis.RedisError as e:
        logger.error(f"Redis error fetching conversation {conversation_id}: {e}")
        raise  # Propagate Redis errors
```

### Performance Considerations

**Current**:
- Read: O(1) Redis GET + O(n) JSON parsing (n = conversation size)
- Write: O(1) Redis SET + O(n) JSON serialization

**Future optimizations** (if needed):
1. **Compression**: `zlib.compress(json_str)` before storing
2. **Message pagination**: Store messages separately, link by index
3. **Lazy loading**: Fetch only recent N messages, load more on demand
4. **Caching**: In-memory cache for active conversations

### Storage Estimate

Typical conversation:
```
- Metadata: ~200 bytes
- Message (user): ~100-500 bytes
- Message (assistant): ~500-2000 bytes
- Message (tool call + result): ~1000-5000 bytes
```

**Example**: 20-message conversation ≈ 20-40 KB

**Redis capacity**: With 2 GB maxmemory, can store ~50,000-100,000 typical conversations.

### Migration Path

If storage format changes:
```python
async def migrate_conversations():
    """Migrate all conversations to new format."""
    keys = await redis.keys("conversation:*")
    
    for key in keys:
        old_data = json.loads(await redis.get(key))
        new_data = transform_to_new_format(old_data)
        await redis.set(key, json.dumps(new_data))
```

## Related Decisions

- **ADR-005**: Global State Pattern - ConversationManager uses this storage approach
- **Architecture**: Sorted set indexing for conversation listing

## References

- [Redis String Commands](https://redis.io/commands/?group=string)
- [Python json module](https://docs.python.org/3/library/json.html)
- [Pydantic Serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)

## Review Notes

- **2025-12-30**: Initial decision - working well for workshop scale
- **Future**: Monitor conversation sizes; consider pagination if frequently >100 messages
- **Future**: If query needs emerge (search by content), consider full-text search (RediSearch) or external search engine
