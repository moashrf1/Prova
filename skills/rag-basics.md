---
name: rag-basics
title: RAG Fundamentals
description: How retrieval-augmented generation works — chunking, embeddings, retrieval, and generation.
category: technical
path: null
tags: [ai, rag, retrieval, embeddings]
---

# RAG Fundamentals

## When to use this
When you want an LLM to answer from your own documents instead of only its training data.

## The pipeline
1. **Chunk** — split documents into passages small enough to be specific, large enough to keep context.
2. **Embed** — convert each chunk into a vector that captures its meaning.
3. **Store** — put vectors in a vector database.
4. **Retrieve** — embed the question, find the closest chunks by similarity.
5. **Generate** — hand the retrieved chunks to the LLM as context to answer from.

## Quality levers
- Chunk size and overlap affect what gets retrieved.
- A reranker after retrieval improves which chunks reach the model.
- The embedding model must match the language of your documents.

## Common trap
Blaming the LLM for a wrong answer when the real problem is retrieval — the right chunk never reached the model. Check what was retrieved first.
