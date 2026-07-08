---
name: prompting-patterns
title: Effective Prompting Patterns
description: Reusable patterns for clearer LLM prompts — role, examples, step-by-step, structured output.
category: technical
path: null
tags: [ai, prompting, llm]
---

# Effective Prompting Patterns

## When to use this
When an LLM's output is inconsistent, off-format, or misses the point.

## Core patterns
- **Be specific and detailed** — vague prompts get vague answers. State the goal, the constraints, and the format.
- **Give examples** (few-shot) — show one or two examples of the input/output you want.
- **Ask for step-by-step reasoning** for complex tasks before the final answer.
- **Request structured output** — ask for JSON or specific tags when you need to parse the result.
- **Positive and negative examples** — show what you want AND what to avoid.

## Common trap
Over-stuffing the prompt with everything at once. Start simple, test, then add constraints only where the output actually fails.
