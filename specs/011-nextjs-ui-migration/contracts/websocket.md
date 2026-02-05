# WebSocket Contract: MITS Chat Streaming

**Endpoint**: `ws://localhost:8000/api/v1/ws/{sessionId}`

## Connection

```javascript
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/${sessionId}`);
```

Connection requires valid session ID. Invalid session returns 404 before upgrade.

---

## Client → Server Messages

### message
Send a chat message to the tutor.

```json
{
  "type": "message",
  "content": "Я думаю, что ответ 2x",
  "timestamp": 1706745600000
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | Yes | Always "message" |
| content | string | Yes | Message text (1-10000 chars) |
| timestamp | integer | Yes | Unix timestamp in milliseconds |

---

### hint_request
Request the next progressive hint.

```json
{
  "type": "hint_request"
}
```

Server responds with hint if available, or error if no hints remaining.

---

### typing_start
Notify server that user started typing (optional, for analytics).

```json
{
  "type": "typing_start"
}
```

---

### typing_stop
Notify server that user stopped typing.

```json
{
  "type": "typing_stop"
}
```

---

## Server → Client Messages

### token
Streaming token from tutor response.

```json
{
  "type": "token",
  "content": "Отлично",
  "is_thinking": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always "token" |
| content | string | Token text (1-50 chars typically) |
| is_thinking | boolean | True if part of CoT reasoning |

**Usage**: Append `content` to message being streamed. If `is_thinking` is true, display in collapsed "thinking" section.

---

### response_complete
Full response after streaming completes.

```json
{
  "type": "response_complete",
  "message_id": "msg_abc123",
  "response": {
    "content": "Отлично! Ты правильно применил правило степени. Производная $x^2$ действительно равна $2x$.",
    "move_type": "encourage",
    "is_correct": true,
    "thinking": "Student correctly applied power rule..."
  },
  "session_state": {
    "is_solved": true,
    "hints_used": 0,
    "attempts": 1,
    "told_answer": false
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always "response_complete" |
| message_id | string | Unique message identifier |
| response.content | string | Full response text |
| response.move_type | string | Tutor move type |
| response.is_correct | boolean? | If answer attempt, correctness |
| response.thinking | string? | Full CoT reasoning |
| session_state.is_solved | boolean | Task completion status |
| session_state.hints_used | integer | Hints used count |
| session_state.attempts | integer | Answer attempts count |
| session_state.told_answer | boolean | Whether answer was revealed |

---

### hint_response
Response to hint_request.

```json
{
  "type": "hint_response",
  "hint_number": 1,
  "hint_text": "Подумай, какое правило применяется для степенной функции?",
  "hints_remaining": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| hint_number | integer | Hint index (1, 2, or 3) |
| hint_text | string | Hint content |
| hints_remaining | integer | Remaining hints available |

---

### knowledge_update
Skill mastery changes after correct/incorrect answer.

```json
{
  "type": "knowledge_update",
  "changes": {
    "power_rule": 0.85,
    "derivatives": 0.72
  },
  "overall_mastery": 0.78
}
```

| Field | Type | Description |
|-------|------|-------------|
| changes | object | Skill → new mastery value |
| overall_mastery | number | Overall topic mastery |

---

### error
Error notification.

```json
{
  "type": "error",
  "code": "LLM_UNAVAILABLE",
  "message": "Репетитор временно недоступен. Проверьте, запущен ли Ollama.",
  "recoverable": true,
  "retry_after": 5
}
```

| Field | Type | Description |
|-------|------|-------------|
| code | string | Error code for programmatic handling |
| message | string | Human-readable message (Russian) |
| recoverable | boolean | Whether client should retry |
| retry_after | integer? | Seconds to wait before retry |

**Error Codes**:
| Code | Description |
|------|-------------|
| LLM_UNAVAILABLE | Ollama not responding |
| SESSION_NOT_FOUND | Invalid session ID |
| RATE_LIMITED | Too many requests |
| INVALID_MESSAGE | Malformed message |
| NO_HINTS_REMAINING | All hints used |
| INTERNAL_ERROR | Unexpected server error |

---

### connection_ready
Sent immediately after connection established.

```json
{
  "type": "connection_ready",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_state": {
    "is_solved": false,
    "hints_used": 0,
    "attempts": 0
  }
}
```

---

## Message Flow Example

```
Client                                  Server
  |                                       |
  |------ WebSocket Connect ------------->|
  |<----- connection_ready ---------------|
  |                                       |
  |------ message (answer: "2x") -------->|
  |<----- token ("Отлично") --------------|
  |<----- token ("!") --------------------|
  |<----- token (" Ты") ------------------|
  |<----- token (" правильно") -----------|
  |<----- ... (more tokens) --------------|
  |<----- response_complete --------------|
  |<----- knowledge_update ---------------|
  |                                       |
  |------ hint_request ------------------>|
  |<----- hint_response ------------------|
  |                                       |
```

---

## Error Handling

### Connection Errors
- **1000 (Normal)**: Clean disconnect
- **1001 (Going Away)**: Server shutdown
- **1008 (Policy Violation)**: Invalid session
- **1011 (Internal Error)**: Server error

### Reconnection Strategy
1. Wait 1 second
2. Attempt reconnect
3. If fails, exponential backoff (2s, 4s, 8s, max 30s)
4. After 5 failures, show error to user

### Message Ordering
- Tokens arrive in order
- `response_complete` always follows all tokens
- `knowledge_update` may arrive after `response_complete`

---

## Frontend Implementation Notes

```typescript
// Accumulate tokens
let streamingContent = '';

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'token':
      streamingContent += data.content;
      updateStreamingMessage(streamingContent, data.is_thinking);
      break;

    case 'response_complete':
      finalizeMessage(data.response, data.session_state);
      streamingContent = '';
      break;

    case 'error':
      if (data.recoverable) {
        showRetryPrompt(data.message, data.retry_after);
      } else {
        showErrorMessage(data.message);
      }
      break;
  }
};
```
