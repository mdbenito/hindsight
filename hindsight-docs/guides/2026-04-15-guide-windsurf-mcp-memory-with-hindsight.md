---
title: "Guide: Set Up Windsurf MCP Memory with Hindsight"
authors: [benfrank241]
date: 2026-04-15
tags: [how-to, windsurf, mcp, memory]
description: "Set up Windsurf MCP memory with Hindsight using Hindsight Cloud or a local MCP server, then test retain, recall, and reflect in a real workflow."
image: /img/blog/guide-windsurf-mcp-memory-with-hindsight.png
hide_table_of_contents: true
---

![Guide: Set Up Windsurf MCP Memory with Hindsight](/img/blog/guide-windsurf-mcp-memory-with-hindsight.png)

If you want **Windsurf MCP memory with Hindsight**, the shortest path is to connect Windsurf to Hindsight's MCP endpoint and let Hindsight supply long-term memory tools. That gives Windsurf a way to retain important facts, recall earlier context, and reflect across previous sessions instead of treating every new conversation like a cold start.

For most teams, [Hindsight Cloud](https://hindsight.vectorize.io) is the easiest setup because Windsurf can connect through the hosted MCP endpoint and complete the OAuth flow in a browser. If you prefer to keep everything local, you can also run Hindsight yourself and point Windsurf at a local MCP server.

This guide covers both approaches, shows the Windsurf-specific config detail that trips people up, and gives you a quick verification flow so you can confirm memory is actually working after setup. Keep the [docs home](https://hindsight.vectorize.io/docs) and the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) open while you work.

<!-- truncate -->

> **Quick answer**
>
> 1. Choose Hindsight Cloud or a local MCP server.
> 2. Add a Hindsight MCP server inside Windsurf's MCP settings.
> 3. Use the correct Windsurf field name, `serverUrl`, when editing config manually.
> 4. Save, reload, and complete OAuth if you are using Cloud.
> 5. Test retain, recall, and reflect with a short memory check.

## Prerequisites

Before you start, make sure you have:

- Windsurf installed
- A Hindsight Cloud account for the hosted path, or a local Hindsight MCP server for the self-hosted path
- Permission to open the OAuth approval browser if you are using Cloud

The hosted route is easier for most people because it avoids manual credential handling and works well across multiple machines.

## Option 1: Use Hindsight Cloud with Windsurf

Inside Windsurf:

1. Open **Settings**.
2. Go to **Cascade → MCP Servers**.
3. Click **Add Server**.
4. Enter `https://mcp.hindsight.vectorize.io` as the server URL.
5. Save and reload Windsurf.

On the next session start, Windsurf should trigger the OAuth flow in your browser. Log in to Hindsight Cloud, approve access, and choose the organization Windsurf should use.

That is enough to get the hosted setup running.

### Manual config note

If you edit Windsurf's config file directly, the important detail is that Windsurf uses `serverUrl` instead of `url`.

Typical config path:

- `~/.codeium/windsurf/mcp_config.json`

Example:

```json
{
  "mcpServers": {
    "hindsight": {
      "serverUrl": "https://mcp.hindsight.vectorize.io"
    }
  }
}
```

That `serverUrl` key is easy to miss if you are copying config from a different MCP client.

## Option 2: Use a local Hindsight MCP server

If you want to run Hindsight yourself, start the local MCP server first.

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

Then point Windsurf at your local MCP endpoint instead:

```json
{
  "mcpServers": {
    "hindsight": {
      "serverUrl": "http://localhost:8888/mcp/"
    }
  }
}
```

For a single dedicated bank, use a bank-specific path such as `http://localhost:8888/mcp/my-bank/`.

## What Hindsight gives Windsurf

After the MCP connection succeeds, Windsurf should be able to use:

- **retain** to save durable facts from work sessions
- **recall** to search for previously stored context
- **reflect** to synthesize what the memory bank contains

That matters because a useful coding assistant needs more than a raw transcript. Hindsight stores structured memory, resolves entities, and ranks recalled items using more than one retrieval strategy. This is what helps a later question surface the right design decision, bug note, or preference instead of a random semantically similar snippet.

For the low-level behavior, read [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain) and [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall).

## Verify the setup

Start with a tool check:

> What memory tools do you have available?

Windsurf should see retain, recall, and reflect.

Then store a quick fact:

> Remember that this repo prefers pnpm, strict TypeScript, and small pull requests.

Open a fresh conversation and ask:

> What do you know about this repo's working style?

If the memory layer is working, Windsurf should recall those preferences without you repeating them.

Then test a synthesis question:

> Based on what you know about this repo, how should I break up a feature branch?

That is a good way to see whether reflect is available and useful.

## Troubleshooting

### Windsurf saves the server, but nothing appears in chat

Reload Windsurf completely. Tool lists are often cached until a fresh start.

### OAuth does not launch

Check whether your environment allows Windsurf to open an external browser. Some work setups block this.

### The config looks correct, but the connection still fails

Make sure you used `serverUrl`, not `url`, if you edited the JSON manually.

### New facts do not recall right away

Retain is asynchronous. Wait a few seconds, then try recall again.

### I want separate memory per project

Use separate banks. You can do that by changing the bank-specific URL in single-bank mode or by routing requests consistently in multi-bank setups.

## When to use Cloud vs local

Use **Hindsight Cloud** if you want:

- easy OAuth onboarding
- less setup work
- access from multiple machines
- cleaner revocation and per-org auth

Use **local MCP** if you want:

- local-only storage and processing
- full control over the environment
- a development sandbox for memory behavior

If you want to compare editor workflows, the [Claude Code integration](https://hindsight.vectorize.io/docs/integrations/claude-code) and [Adding Memory to Codex with Hindsight](https://hindsight.vectorize.io/blog/adding-memory-to-codex-with-hindsight) are both useful reference points.

## FAQ

### Does Windsurf need a Hindsight API key for Cloud?

No. The Hindsight Cloud route is designed to work through OAuth.

### Can several people share memory in Windsurf?

Yes, if they are routed to the same bank design intentionally. The key question is how you want to scope banks, not whether MCP supports it.

### Is the local MCP server feature-complete?

Yes. The local MCP server exposes the full Hindsight API and tool set.

### Do I need a custom prompt for memory to work?

No. The MCP integration exposes the tools directly. Prompting can still help guide when tools are used, but the core connection does not depend on a giant custom prompt.

## Next Steps

- Sign up for [Hindsight Cloud](https://hindsight.vectorize.io) if you want the fastest Windsurf setup
- Read the [full Hindsight docs](https://hindsight.vectorize.io/docs)
- Follow the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart)
- Review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall)
- Review [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain)
- Compare coding workflows in [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents)
