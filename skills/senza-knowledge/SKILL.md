---
name: senza-knowledge
description: >-
  Knowledge, memory, and session-recall for Senza agents. Use when the user
  wants to: (1) give an agent a local document knowledge base (RAG),
  (2) let an agent write/forget long-term memories,
  (3) recall relevant context from past sessions,
  (4) build a knowledge_search + knowledge_read tool pair,
  (5) build a memory_write + memory_forget tool pair,
  (6) build a history_recall plugin for cross-session context.
  Trigger phrases: "knowledge source", "RAG", "memory plugin", "memory store",
  "session recall", "history recall", "knowledge_search", "knowledge_read",
  "memory_write", "memory_forget", "local knowledge", "long-term memory".
---

# Senza Knowledge — RAG, Memory, and Session Recall

> SDK: `import senza`
> Prerequisites: read `senza-agent` skill first.

## Overview

Three subsystems, each following a create → install → build pattern:

| Subsystem | Tools exposed | Key components |
|-----------|---------------|----------------|
| Knowledge (RAG) | `knowledge_search`, `knowledge_read` | `KnowledgeSource` + `KnowledgePlugin` |
| Memory | `memory_write`, `memory_forget` | `KnowledgeSource` + `MemoryStore` + `MemoryWritePolicy` + `MemoryPlugin` |
| Session Recall | (background context injection) | `SessionRecallIndex` + `SessionRepo` + `SessionRecallKnowledgeSource` + `HistoryRecallPlugin` |

---

## 1. Knowledge (RAG)

### LocalDocumentSource

```python
senza.create_local_knowledge_source(
    path: str,
    source_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    domains: Optional[list[str]] = None,
    max_document_bytes: int = 1048576,
) -> KnowledgeSource
```

Creates a knowledge source backed by a local directory of documents.
The source is indexed on creation and searched via the `knowledge_search` tool.

| Parameter | Description |
|-----------|-------------|
| `path` | Directory containing documents (`.md`, `.txt`, etc.) |
| `source_id` | **Unique identifier** — must match `read_source_id` when pairing with a memory store |
| `name` | Human-readable name (shown to LLM) |
| `description` | What this source contains |
| `domains` | Domain tags for filtering |
| `max_document_bytes` | Per-document size cap (default 1 MB) |

### KnowledgePlugin

```python
senza.create_knowledge_plugin(
    sources: list[KnowledgeSource],
    config: Optional[dict] = None,
) -> Plugin
```

Registers two tools the LLM can call:
- `knowledge_search(query)` — semantic search across all sources, returns ranked chunks.
- `knowledge_read(source_id, doc_id)` — fetch a full document by ID.

### RAG Pattern

```python
import senza

provider = senza.create_openai_provider(api_key="sk-...")

# 1. Create local knowledge source
docs = senza.create_local_knowledge_source(
    path="/data/wiki",
    source_id="wiki",
    name="Internal Wiki",
    description="Team wiki and runbooks",
)

# 2. Create knowledge plugin
knowledge = senza.create_knowledge_plugin(sources=[docs])

# 3. Install on builder
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(knowledge)
    .build()
)

# The LLM can now call knowledge_search("how to deploy") and
# knowledge_read("wiki", "deploy-guide") autonomously.
```

Multiple sources:

```python
wiki = senza.create_local_knowledge_source(
    path="/data/wiki", source_id="wiki",
)
runbooks = senza.create_local_knowledge_source(
    path="/data/runbooks", source_id="runbooks",
)

knowledge = senza.create_knowledge_plugin(sources=[wiki, runbooks])
```

---

## 2. Long-Term Memory

### InMemoryStore

```python
senza.create_in_memory_store(read_source_id: str) -> MemoryStore
```

An in-memory key-value store the agent can write to and read from.
`read_source_id` **must match** the `source_id` of the paired `KnowledgeSource` —
this is how the memory plugin reads back what it wrote.

> **CRITICAL**: If `source_id` and `read_source_id` don't match, writes will
> succeed but reads will return nothing.

### SecureMemoryWritePolicy

```python
senza.create_secure_write_policy(config: Optional[dict] = None) -> MemoryWritePolicy
```

A write policy that validates memory writes against injection and size
constraints. Prevents the agent from storing adversarial content.
Config dict supports tuning these limits.

### MemoryMutationGate (optional)

```python
senza.create_allow_all_gate() -> MemoryMutationGate
```

A permissive gate — all writes pass. Use for development / trusted environments.
Pass as the `gate` argument to `create_memory_plugin` to override the default
secure gate.

### MemoryPlugin

```python
senza.create_memory_plugin(
    source: KnowledgeSource,
    store: MemoryStore,
    policy: MemoryWritePolicy,
    gate: Optional[MemoryMutationGate] = None,
) -> Plugin
```

Registers two tools:
- `memory_write(key, content)` — persist a memory entry (validated by policy + gate).
- `memory_forget(key)` — delete a memory entry.

The plugin also makes written memories searchable via `knowledge_search` because
the store's `read_source_id` is linked to the source.

### Memory Pattern

```python
import senza

provider = senza.create_openai_provider(api_key="sk-...")

# 1. Create a local knowledge source for memory storage
mem_source = senza.create_local_knowledge_source(
    path="/data/memory",
    source_id="memory",          # ← this ID...
)

# 2. Create in-memory store with MATCHING read_source_id
store = senza.create_in_memory_store(
    read_source_id="memory",     # ← ...must match!
)

# 3. Create secure write policy
policy = senza.create_secure_write_policy()

# 4. Create memory plugin
memory = senza.create_memory_plugin(
    source=mem_source,
    store=store,
    policy=policy,
)

# 5. Install
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(memory)
    .build()
)

# The LLM can now call memory_write("user_prefs", "prefers concise answers")
# and memory_forget("user_prefs").
```

Combining knowledge + memory:

```python
# RAG for documents + writable memory — both in one harness
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_knowledge_plugin(sources=[docs]))
    .plugin(senza.create_memory_plugin(
        source=mem_source, store=store, policy=policy,
    ))
    .build()
)
```

---

## 3. Session Recall

Recall relevant context from past agent sessions automatically.

### SessionRecallIndex

```python
senza.create_in_memory_session_recall_index() -> SessionRecallIndex
senza.create_sqlite_session_recall_index(path: str) -> SessionRecallIndex
```

Indexes session transcripts for semantic recall. Use the SQLite variant for
persistence across restarts:

```python
index = senza.create_sqlite_session_recall_index("/data/recall.db")
```

### SessionRepo

```python
senza.create_in_memory_session_repo() -> SessionRepo
```

Stores raw session data (messages, metadata). In-memory by default.

### SessionRecallKnowledgeSource

```python
senza.create_session_recall_knowledge_source(
    repo: SessionRepo, index: SessionRecallIndex,
) -> SessionRecallKnowledgeSource
```

Bridges the repo + index into a `KnowledgeSource`-compatible interface.
Call `.as_knowledge_source()` to get a `KnowledgeSource` that can be passed
to `create_knowledge_plugin`:

```python
recall_source = senza.create_session_recall_knowledge_source(repo, index)
ks = recall_source.as_knowledge_source()
```

### HistoryRecallPlugin

```python
senza.create_history_recall_plugin(
    source: SessionRecallKnowledgeSource,
    config: Optional[dict] = None,
) -> Plugin
```

Automatically injects relevant past-session context into the current turn.
Unlike `KnowledgePlugin` (which exposes tools the LLM calls), this plugin
works in the background — it retrieves relevant history and adds it to the
context before each LLM call.

### Session Recall Pattern

```python
import senza

provider = senza.create_openai_provider(api_key="sk-...")

# 1. Create index + repo
index = senza.create_sqlite_session_recall_index("/data/recall.db")
repo = senza.create_in_memory_session_repo()

# 2. Create knowledge source from repo + index
recall_source = senza.create_session_recall_knowledge_source(repo, index)

# 3. Create history recall plugin
recall_plugin = senza.create_history_recall_plugin(recall_source)

# 4. Install
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(recall_plugin)
    .build()
)

# Past session context is now automatically recalled and injected.
```

Using recall source as a regular knowledge source (LLM calls
`knowledge_search` explicitly):

```python
recall_source = senza.create_session_recall_knowledge_source(repo, index)
ks = recall_source.as_knowledge_source()

harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_knowledge_plugin(sources=[ks]))
    .build()
)
```

---

## Quick Reference

| Function | Returns | Purpose |
|----------|---------|---------|
| `create_local_knowledge_source(path, source_id, ...)` | `KnowledgeSource` | Local document RAG source |
| `create_knowledge_plugin(sources, config=None)` | `Plugin` | `knowledge_search` + `knowledge_read` tools |
| `create_in_memory_store(read_source_id)` | `MemoryStore` | Writable in-memory store |
| `create_secure_write_policy(config=None)` | `MemoryWritePolicy` | Injection-safe write validation |
| `create_allow_all_gate()` | `MemoryMutationGate` | Permissive write gate |
| `create_memory_plugin(source, store, policy, gate=None)` | `Plugin` | `memory_write` + `memory_forget` tools |
| `create_in_memory_session_recall_index()` | `SessionRecallIndex` | In-memory session index |
| `create_sqlite_session_recall_index(path)` | `SessionRecallIndex` | Persistent SQLite session index |
| `create_in_memory_session_repo()` | `SessionRepo` | In-memory session storage |
| `create_session_recall_knowledge_source(repo, index)` | `SessionRecallKnowledgeSource` | Bridge repo+index to knowledge source |
| `.as_knowledge_source()` | `KnowledgeSource` | Convert recall source to standard KS |
| `create_history_recall_plugin(source, config=None)` | `Plugin` | Auto-inject past-session context |
