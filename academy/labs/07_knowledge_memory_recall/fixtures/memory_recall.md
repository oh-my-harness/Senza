# Senza Memory and Session Recall Boundaries

The built-in Senza MemoryStore is an in-process demo backed by `Mutex<Vec>`.
It is not persistent. `memory_write` and `memory_forget` operate on that store,
but a write does not automatically synchronize into `local_source` or become
searchable through `knowledge_search`.

Session Recall exposes repo, index, knowledge-source, and plugin contracts.
The current Python surface does not expose the projector or index-population
path required to demonstrate an honest end-to-end recall flow.
