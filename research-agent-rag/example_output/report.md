# RAG evolution: what our knowledge base says vs. how the concept has evolved

## 1) What the knowledge base says RAG is (baseline definition)
Our knowledge base frames retrieval-augmented generation (RAG) primarily as a *two-stage pipeline* that (1) retrieves relevant documents from an external corpus and (2) injects them into the LLM’s prompt to produce an answer grounded in those sources. The key emphasis is on supplementing the model’s static, parametric training data with *domain-specific and/or up-to-date* information at query time, improving relevance and factuality by “looking things up” in a specified document set rather than relying only on memory.

In short: **retrieve passages → concatenate into context → generate**.

## 2) How current sources show RAG has expanded beyond “retrieve then generate”
Recent work characterizes modern RAG as a broader design space with many architectural variants and control mechanisms, driven by the practical problems that naive RAG exposes (retrieval noise, redundancy, faithfulness gaps, latency/cost, and brittleness).

A 2025 survey describes RAG research as spanning retriever-centric, generator-centric, hybrid, and robustness-oriented designs, explicitly calling out tensions like retrieval precision vs. generation flexibility and efficiency vs. faithfulness. It highlights active areas including retrieval optimization, context filtering, decoding control, and efficiency improvements—i.e., *RAG as an end-to-end system* rather than a fixed pattern.

## 3) Agentic / iterative RAG: dynamic control over when and how to retrieve
A notable evolution is the shift from static, linear pipelines to **adaptive and iterative** workflows where the system decides when retrieval is needed, reformulates queries, and may loop through retrieve→reason→retrieve.

Self-RAG (2023; ICLR 2024) targets a specific weakness of “fixed top-k retrieval”: retrieving even when it’s unnecessary and accepting irrelevant passages that degrade output. It introduces **on-demand retrieval** plus **self-critique**: the model emits special “reflection tokens” that (a) trigger retrieval only when useful and (b) critique/check the quality and support of its own generations, improving factuality and citation accuracy.

A 2026 survey synthesizes this trajectory under **Agentic RAG**, where autonomous agent patterns (planning, reflection, tool use, multi-step workflows, even multi-agent collaboration) are embedded in the RAG loop to improve adaptability for complex tasks.

## 4) Structured retrieval (GraphRAG): moving beyond chunk similarity for “global” questions
Another evolution is augmenting (or partially replacing) pure vector similarity over chunks with **structured representations**.

Microsoft Research’s GraphRAG (2024) uses an LLM to extract a **knowledge graph** from a document collection and then produces **hierarchical “community” summaries**. The motivation is that naive top-k chunk retrieval fails on *global* questions (e.g., “What are the main themes in the dataset?”) because it only considers a small subset of similar chunks, which can be misleading. GraphRAG instead supports dataset-wide questions via a map-reduce style process over community summaries, trading upfront indexing cost for improved global coverage.

## 5) Summary of the evolution (practical deltas)
Compared with the KB’s baseline description, current sources suggest RAG has evolved along these axes:

- **From fixed to adaptive retrieval**: retrieve *only when needed*; re-retrieve iteratively; revise queries (Self-RAG; Agentic RAG survey).
- **From “stuff documents into prompt” to controlled evidence use**: filtering, evaluation of evidence quality, and mechanisms that reduce hallucinations/faithfulness gaps (2025 survey).
- **From unstructured chunks to structured indexes**: graphs and hierarchical summaries to answer questions that require *global* corpus understanding (GraphRAG).
- **From a technique to a system discipline**: explicit attention to latency/cost, robustness, evaluation, and deployment trade-offs (2025 survey; GraphRAG).

## Sources
- retrieval-augmented-generation.pdf (knowledge base), pp. 1–2
- large-language-model.pdf (knowledge base), p. 8
- https://arxiv.org/html/2506.00054v1
- https://arxiv.org/abs/2310.11511
- https://arxiv.org/html/2310.11511v1
- https://www.microsoft.com/en-us/research/blog/graphrag-new-tool-for-complex-data-discovery-now-on-github/
- https://arxiv.org/html/2501.09136v4
