---
name: sql-query-optimization
title: SQL Query Optimization
description: Techniques to make SQL queries faster — indexing, avoiding N+1, reading query plans.
category: technical
path: null
tags: [sql, performance, database]
---

# SQL Query Optimization

## When to use this
Reach for this when a query is slow, a report times out, or a dashboard lags.

## Core ideas
- **Indexes** speed up lookups on columns you filter or join on, but slow down writes. Index the columns in your WHERE and JOIN clauses, not every column.
- **N+1 problem**: running one query per row in a loop. Replace with a single JOIN or a batched query.
- **Read the query plan** (`EXPLAIN`) to see whether the database scans the whole table or uses an index. A "full table scan" on a large table is the usual culprit.
- **Select only needed columns** — `SELECT *` pulls data you don't use and defeats covering indexes.

## Common trap
Adding an index and seeing no improvement usually means the query isn't using it — check the plan, and confirm the filtered column matches the indexed column exactly (no function wrapping it).
