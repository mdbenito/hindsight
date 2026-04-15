---
title: "Guide: Set Up Cursor MCP Memory with Hindsight"
authors: [benfrank241]
date: 2026-04-15
tags: [how-to, cursor, mcp, memory]
description: "Set up Cursor MCP memory with Hindsight using Hindsight Cloud or a local MCP server, then verify recall, retain, and reflect all work correctly."
image: /img/blog/guide-cursor-mcp-memory-with-hindsight.png
hide_table_of_contents: true
---

![Guide: Set Up Cursor MCP Memory with Hindsight](/img/blog/guide-cursor-mcp-memory-with-hindsight.png)

If you want **Cursor MCP memory with Hindsight**, the fastest path is to connect Cursor to Hindsight's MCP endpoint and let Hindsight handle retain, recall, and reflect for you. That gives Cursor long-term memory across sessions without building your own vector store, custom retrieval pipeline, or prompt stuffing routine.

The easiest setup uses [Hindsight Cloud](https://hindsight.vectorize.io), because Cursor can authorize with OAuth and start using memory tools immediately. If you prefer to keep everything local, you can also run Hindsight on your machine and point Cursor at a local MCP endpoint. In both cases, the result is the same: Cursor gets persistent memory tools that survive new chats and new work sessions.

This guide walks through both setup paths, how to verify the tools are live, and what to check if Cursor connects but memory does not show up yet. Keep the [Hindsight docs](https://hindsight.vectorize.io/docs) and the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) handy while you work.

<!-- truncate -->

> **Quick answer**
>
> 1. Decide whether you want Hindsight Cloud or a local MCP server.
> 2. Add the Hindsight MCP endpoint in Cursor under **Settings → Features → MCP Servers**.
> 3. Complete the OAuth flow for Cloud, or add your local or API-key-backed endpoint manually.
> 4. Restart Cursor if the tools do not appear immediately.
> 5. Test `retain`, `recall`, and `reflect` with a short memory check.

## Prerequisites

Before you start, make sure you have:

- A working Cursor install
- A Hindsight account if you want the hosted path
- Or a running local Hindsight MCP server if you want everything on your own machine
- Permission to open an external browser for OAuth if you use Hindsight Cloud

If you are new to Hindsight, start with [Hindsight Cloud](https://hindsight.vectorize.io). It is the quickest route because you do not need to run infrastructure before Cursor can use memory.

## Option 1: Connect Cursor to Hindsight Cloud

For most people, this is the best path.

1. Open **Cursor Settings**.
2. Go to **Features → MCP Servers**.
3. Click **Add MCP Server**.
4. Enter `https://mcp.hindsight.vectorize.io` as the server URL.
5. Set the transport to **HTTP**.
6. Save the server.

On first use, Cursor should open a browser window for the OAuth approval flow. Log in to your Hindsight account, approve access, and choose the organization you want Cursor to use.

Once approved, Cursor should expose Hindsight memory tools automatically. That means you can ask Cursor to remember facts, search prior context, or synthesize what it knows from earlier work.

Why this is the preferred setup:

- no API keys to copy into Cursor
- no local database or service to maintain
- easy to use across multiple machines
- simple per-user auth and revocation

If your team wants shared memory later, you can point several tools at the same bank strategy, similar to the pattern in [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents).

## Option 2: Connect Cursor to a local Hindsight MCP server

If you want local control, start Hindsight on your machine first.

With a cloud LLM provider:

```bash
HINDSIGHT_API_LLM_API_KEY=your_llm_key uvx --from hindsight-api hindsight-local-mcp
```

With Ollama:

```bash
HINDSIGHT_API_LLM_PROVIDER=ollama \
HINDSIGHT_API_LLM_MODEL=llama3.2 \
uvx --from hindsight-api hindsight-local-mcp
```

That starts the local MCP server on `http://localhost:8888/mcp/`.

Then in Cursor:

1. Open **Settings → Features → MCP Servers**.
2. Add a new MCP server.
3. Use `http://localhost:8888/mcp/` for multi-bank mode, or `http://localhost:8888/mcp/my-bank/` for a single dedicated bank.
4. Save and reload Cursor.

If you want more background on local MCP mode, the [local MCP server docs](https://hindsight.vectorize.io/docs) and the [recall API reference](https://hindsight.vectorize.io/docs/api/recall) are useful follow-ups.

## What the memory tools actually do

Once connected, Cursor should have three core memory operations available:

- **retain** stores information to long-term memory
- **recall** searches prior memories and returns relevant context
- **reflect** reasons across stored memories and summarizes what matters

This is where Hindsight differs from a plain conversation log. Hindsight stores more than raw messages. It extracts facts, tracks entities, and uses multiple retrieval strategies before reranking results. That is why a later question like “what did we decide about caching?” can work even if the original note used different words.

For implementation detail, see [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain) and [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall).

## Verify that Cursor memory is working

After connecting Cursor, run a quick memory test.

First, ask Cursor what MCP tools it sees:

> What memory tools do you have available?

It should mention retain, recall, and reflect.

Then teach it a small fact:

> Remember that my default stack for new side projects is Next.js, Postgres, and TypeScript.

Open a fresh chat and ask:

> What do you know about my preferred stack for side projects?

If the setup is correct, Cursor should recall that fact without you repeating it.

A good second test is a synthesis question:

> Based on what you know about my stack preferences, what starter architecture would you suggest?

That should trigger reflect behavior instead of simple recall.

## Common errors and fixes

### Cursor connected, but no tools appear

Reload Cursor or restart it completely. Some MCP clients cache tool availability at startup.

### The OAuth browser never opens

Check whether Cursor is allowed to open an external browser. Some environments block this, especially on locked-down work machines.

### The server saves, but calls fail

Double-check that you used the correct transport and URL. For Hindsight Cloud, the MCP endpoint is `https://mcp.hindsight.vectorize.io`. For local use, it is your local `http://localhost:8888/mcp/` path.

### Memory works in one chat, but not later

Make sure you are still using the same bank. In single-bank mode the bank is pinned in the URL. In multi-bank setups, your app or tool configuration needs to keep bank routing consistent.

### Newly saved facts do not show up immediately

Retain is asynchronous. Wait a few seconds, then try recall again.

## When to use Cloud vs local

Use **Hindsight Cloud** if you want the quickest setup and easiest OAuth flow.

Use **local MCP** if you want all data and operations to stay on your machine, or if you are testing memory behavior before deciding how to deploy it more broadly.

If you later want a coding workflow that auto-injects memory into another tool, the [Claude Code integration](https://hindsight.vectorize.io/docs/integrations/claude-code) and [Adding Memory to Codex with Hindsight](https://hindsight.vectorize.io/blog/adding-memory-to-codex-with-hindsight) are both useful comparison points.

## FAQ

### Does Cursor need an API key for Hindsight Cloud?

No, not if you use the OAuth flow through Hindsight Cloud. That is the main convenience of the hosted setup.

### Can I keep memory separate per project?

Yes. The cleanest way is to use different banks for different projects, or pin a dedicated single-bank endpoint for each environment.

### Is local MCP enough for real work?

Yes. The local server runs the full Hindsight API and MCP endpoint, not a toy subset.

### What if I only want recall, not retain?

That is possible at the application level, but for most Cursor workflows you will want all three memory operations available.

## Next Steps

- Sign up for [Hindsight Cloud](https://hindsight.vectorize.io) if you want the fastest Cursor setup
- Read the [full Hindsight docs](https://hindsight.vectorize.io/docs)
- Work through the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart)
- Review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall)
- Review [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain)
- Compare team workflows in [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents)
