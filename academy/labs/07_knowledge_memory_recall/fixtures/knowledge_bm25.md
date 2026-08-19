# Senza Local Knowledge with BM25

`senza.knowledge.local_source` indexes local Markdown and text documents with
BM25 lexical retrieval. `senza.knowledge.plugin` contributes the
`knowledge_search` and `knowledge_read` tools. This local implementation is not
a dense vector database, hybrid retriever, or reranker. A live Provider can
choose `knowledge_search`, inspect evidence, and then read a selected document.
