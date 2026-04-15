---
title: "Guide: Claude Desktop Memory with Hindsight Cloud"
authors: [benfrank241]
date: 2026-04-15
tags: [how-to, claude-desktop, mcp, memory]
description: "Set up Claude Desktop memory with Hindsight Cloud through MCP and OAuth, then verify retain, recall, and reflect work across separate chats."
image: /img/blog/guide-claude-desktop-memory-with-hindsight-cloud.png
hide_table_of_contents: true
---

![Guide: Claude Desktop Memory with Hindsight Cloud](/img/blog/guide-claude-desktop-memory-with-hindsight-cloud.png)

If you want **Claude Desktop memory with Hindsight Cloud**, the cleanest setup is to add Hindsight as an MCP server and let Claude Desktop authorize through OAuth. That gives Claude persistent memory across separate chats without manually pasting context or managing a local vector database.

Claude Desktop is a good fit for Hindsight because the MCP flow is simple, the tools show up directly inside Claude, and you can keep memory scoped to the organization you authorize. Instead of re-explaining your stack, preferences, or project history every time you open a new conversation, Claude can recall or reflect on what was already stored.

This guide shows the hosted setup first, because it is the easiest one to live with. It also explains what to verify after installation and how to fix the most common issues when the connection succeeds but the memory tools are missing. Keep the [docs home](https://hindsight.vectorize.io/docs) and the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) nearby while you work.

<!-- truncate -->

> **Quick answer**
>
> 1. Edit the Claude Desktop MCP config file.
> 2. Add Hindsight Cloud as an MCP server at `https://mcp.hindsight.vectorize.io`.
> 3. Restart Claude Desktop and complete the OAuth approval flow.
> 4. Ask Claude which memory tools are available.
> 5. Test retain, recall, and reflect across two separate conversations.

## Prerequisites

Before you start, make sure you have:

- Claude Desktop installed
- A Hindsight Cloud account
- Permission to open the OAuth approval window in your browser
- An account role that can authorize the integration for the target organization

For most people, [Hindsight Cloud](https://hindsight.vectorize.io) is the right choice here. Claude Desktop can use OAuth directly, so there is no need to generate and paste an API key just to get memory running.

## Step 1: Find the Claude Desktop config file

Claude Desktop reads MCP servers from a local config file.

Typical locations:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

If the file does not exist yet, create it.

## Step 2: Add Hindsight Cloud as an MCP server

Put this in the config file:

```json
{
  "mcpServers": {
    "hindsight": {
      "url": "https://mcp.hindsight.vectorize.io"
    }
  }
}
```

Save the file and restart Claude Desktop.

On the next startup, Claude Desktop should open a browser window and ask you to authorize Hindsight Cloud. Log in, approve access, and select the organization Claude should use.

That is the whole hosted setup. Once approved, Claude Desktop should expose Hindsight memory tools inside the app.

## Why Hindsight Cloud is the easiest path

You can run Hindsight locally, but Claude Desktop works especially well with the hosted OAuth flow because:

- there is no API key copy and paste step
- token rotation happens automatically
- each client can be revoked independently
- you can connect the same account on multiple devices with the same pattern

If your goal is simply to give Claude persistent memory without infrastructure work, Cloud is the shortest path from zero to useful recall.

## What Claude gets after the connection

Once the MCP server is live, Claude Desktop should be able to use:

- **retain** to save important facts and conversation outcomes
- **recall** to search memory when past context matters
- **reflect** to reason across stored memories and produce a synthesis

This is more useful than a long pasted system prompt because Hindsight is not just storing raw chat logs. It extracts facts, tracks entities, and retrieves what is relevant when you ask for it.

If you want the lower-level details, review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall) and [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain).

## Step 3: Verify it works

Start with a simple tool check:

> What memory tools do you have available?

Claude should mention the Hindsight memory operations.

Then store a clear fact:

> Remember that I prefer concise status updates and TypeScript examples.

Open a separate chat and ask:

> What do you know about my response preferences?

If memory is working, Claude should surface the saved preference without you restating it.

Then test a synthesis prompt:

> Based on what you know about how I like answers, how should you format a migration plan for me?

That should encourage reflect rather than just literal recall.

## Optional: local MCP instead of Cloud

If you want everything on your own machine, you can run the local MCP server first:

```bash
HINDSIGHT_API_LLM_API_KEY=your_llm_key uvx --from hindsight-api hindsight-local-mcp
```

Then point Claude Desktop at your local endpoint instead. The general MCP shape is the same, but local use does not give you the built-in Cloud OAuth flow, which is why Cloud remains the easier default for this client.

If you want more background on the local route, the [full docs](https://hindsight.vectorize.io/docs) and the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) are the best next reads.

## Troubleshooting

### Claude Desktop restarts, but the tools do not appear

Restart the app one more time. Some MCP clients only refresh the tool list on a clean startup.

### The browser approval window never opens

Check whether your OS or security tooling is blocking browser launches from desktop apps.

### Authorization succeeds, but Claude still acts stateless

Run the explicit retain and recall test above. If the tools are present but no memory comes back, you may be testing too quickly after retain. Give indexing a few seconds and try again.

### I have access to multiple organizations

During authorization, choose the org you actually want Claude to use. The connection is scoped per org, not globally.

### I see a permissions error during authorization

Only the right account roles can approve the connection. If you are not an admin or owner for that org, the approval step can fail.

## When this setup works best

Claude Desktop plus Hindsight Cloud is especially good when:

- you use Claude across many separate chats
- you want your personal preferences and project history to compound over time
- you do not want to run a local memory service yourself
- you want memory that is better than a giant saved prompt

If you later want a code-focused workflow with hook-based memory injection, compare this setup with the [Claude Code integration](https://hindsight.vectorize.io/docs/integrations/claude-code). If you want a broader cross-tool pattern, [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents) is a useful complement.

## FAQ

### Does Claude Desktop need a Hindsight API key?

Not for the Hindsight Cloud OAuth flow. That is one of the main reasons this setup is convenient.

### Can Claude Desktop share memory with another tool?

Yes, if both tools are routed to the same bank strategy and organization.

### Can I keep memory isolated by project or user?

Yes. The important part is how you structure banks and routing. The MCP setup gets Claude connected, and bank design controls what memory is shared.

### Is this better than copying notes into every chat?

Yes, because the memory layer can accumulate over time and retrieve only relevant facts later instead of making you maintain a giant reusable prompt by hand.

## Next Steps

- Sign up for [Hindsight Cloud](https://hindsight.vectorize.io) if you have not already
- Browse the [full Hindsight docs](https://hindsight.vectorize.io/docs)
- Follow the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart)
- Review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall)
- Review [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain)
- Compare with the [Claude Code integration](https://hindsight.vectorize.io/docs/integrations/claude-code)
