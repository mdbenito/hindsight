---
title: "Guide: Add Vercel AI SDK Memory with Hindsight"
authors: [benfrank241]
date: 2026-04-15
tags: [how-to, ai-sdk, vercel, memory]
description: "Add Vercel AI SDK memory with Hindsight using ready-to-use tools for retain, recall, and reflect in generateText, streamText, and route handlers."
image: /img/blog/guide-vercel-ai-sdk-memory-with-hindsight.png
hide_table_of_contents: true
---

![Guide: Add Vercel AI SDK Memory with Hindsight](/img/blog/guide-vercel-ai-sdk-memory-with-hindsight.png)

If you want **Vercel AI SDK memory with Hindsight**, the core pattern is to create a Hindsight client, generate Hindsight tools for a bank ID, and pass those tools into your AI SDK workflow. That gives your app durable memory operations, not just conversation state inside the current request.

This matters because the Vercel AI SDK is excellent for generation, streaming, and tool orchestration, but it does not provide long-term memory by itself. If you want an app that remembers the user across requests, across restarts, or across channels, you need a separate memory layer. Hindsight fills that gap with ready-to-use tools for retain, recall, reflect, and related lookup operations.

This guide covers the installation, a working setup for `generateText`, a streaming example, the per-request bank ID pattern you need for multi-user apps, and a few verification checks so you know memory is really attached to the app rather than just implied in the prompt. Keep the [docs home](https://hindsight.vectorize.io/docs) and the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) nearby while you build.

<!-- truncate -->

> **Quick answer**
>
> 1. Install the Hindsight AI SDK package.
> 2. Create a Hindsight client.
> 3. Build tools with `createHindsightTools(...)` and a bank ID.
> 4. Pass those tools into `generateText`, `streamText`, or your agent loop.
> 5. Verify that a later request can recall what an earlier request retained.

## Prerequisites

Before you start, make sure you have:

- A Node.js app already using the Vercel AI SDK
- A running Hindsight backend or a Hindsight Cloud account
- A stable bank ID strategy, usually per user or per tenant
- A place in your app where tool creation can happen with request-specific context

The bank ID decision is the important one. If you hardcode one global bank too early, unrelated users will share memory they should not share.

## Step 1: Install the package

Install the integration and client packages:

```bash
npm install @vectorize-io/hindsight-ai-sdk @vectorize-io/hindsight-client ai
```

That gives you the memory tools layer plus the core Hindsight client.

## Step 2: Create the Hindsight client

Create the client once where you handle app infrastructure.

```typescript
import { HindsightClient } from '@vectorize-io/hindsight-client';

const hindsight = new HindsightClient({
  apiKey: process.env.HINDSIGHT_API_KEY,
  baseUrl: process.env.HINDSIGHT_API_URL,
});
```

If you are using Hindsight Cloud, point `baseUrl` at the Cloud API. If you are self-hosting, use your own API URL.

## Step 3: Create memory tools for the current bank

The integration package gives you five ready-to-use tools. The most important design choice is that **the bank ID is fixed when you create the tools**.

That means in a multi-user app you should usually create tools inside the request handler, where you already know which user the request belongs to.

```typescript
import { createHindsightTools } from '@vectorize-io/hindsight-ai-sdk';

const bankId = `user:${user.id}`;

const tools = createHindsightTools({
  client: hindsight,
  bankId,
});
```

This is the right place to encode tenant or user isolation. It is the same idea you would use in any shared memory system, and it is safer than letting the model decide where memory should go.

## Step 4: Use the tools with `generateText`

A simple `generateText` example looks like this:

```typescript
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const result = await generateText({
  model: openai('gpt-4o-mini'),
  tools,
  prompt: 'Remember that this user prefers weekly summaries on Fridays.',
});
```

In a real application, you usually want your assistant to retain useful information and recall context in later requests. The tool interface makes that possible without writing a separate memory service layer inside your app.

## Step 5: Use the tools with `streamText`

The same tools work with streaming flows:

```typescript
import { streamText } from 'ai';
import { openai } from '@ai-sdk/openai';

const result = await streamText({
  model: openai('gpt-4o-mini'),
  tools,
  prompt: 'Based on what you know about this user, draft a short project update.',
});
```

This is useful because it means you do not have to maintain one memory approach for synchronous generation and another for streaming UIs.

## Step 6: Use a per-request bank ID in route handlers

For multi-user apps, the key pattern is creating tools inside the request path so the bank ID closes over the current user.

```typescript
export async function POST(req: Request) {
  const { userId, message } = await req.json();

  const tools = createHindsightTools({
    client: hindsight,
    bankId: `user:${userId}`,
  });

  const result = await generateText({
    model: openai('gpt-4o-mini'),
    tools,
    prompt: message,
  });

  return Response.json({ text: result.text });
}
```

This is the pattern to prefer in a Next.js route, an API handler, or any backend action where a specific user or tenant is already known.

## What tools the integration provides

The AI SDK integration registers five tools. The most important ones are:

- **retain** to store facts or conversation content
- **recall** to search memory
- **reflect** to synthesize what has been learned
- helper lookup tools for mental models or documents when needed

The important design split is this:

- the **agent** provides semantic input, like what to store or what to search for
- the **application** controls infrastructure choices, like budget, tags, metadata, and the bank ID

That is a good separation because it prevents the model from making routing and cost decisions your app should own.

If you want to understand the runtime behavior more deeply, review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall) and [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain).

## Verify that memory actually works

A good verification flow is:

1. Send a first request that causes the agent to retain a specific fact.
2. Send a second request from the same bank ID that asks about that fact.
3. Send a third request from a different bank ID and confirm the memory does not leak across users.

Example:

- Request 1: “Remember that this user deploys everything on Railway.”
- Request 2: “What platform does this user use for deployment?”
- Request 3 with a different user ID: “What platform do I deploy on?”

If the second request remembers and the third does not, your bank routing is working.

## Common mistakes

### Creating tools once globally for every user

This is the easiest way to create accidental shared memory. In most applications, create the tools inside the request so the correct bank ID is captured per user.

### Treating conversation history as memory

Message history and long-term memory solve different problems. History keeps the current exchange coherent. Hindsight stores facts that should survive later requests.

### Letting the model choose the bank ID

Do not do that. Bank routing is application logic.

### Forgetting to verify isolation

Always test with two users, not one. A memory system that remembers the right facts for the wrong user is worse than no memory system at all.

## FAQ

### Does this only work with `generateText`?

No. The same tools work with `streamText` and agent-style loops as well.

### Do I need Hindsight Cloud?

No. Self-hosted Hindsight works too.

### Is one bank per user always the right approach?

Not always. Sometimes one bank per team, workspace, or project makes more sense. The key is to make that choice explicitly.

### Can I combine this with a shared coding workflow?

Yes. If you want to compare patterns, [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents) and [Adding Memory to Codex with Hindsight](https://hindsight.vectorize.io/blog/adding-memory-to-codex-with-hindsight) are useful related reads.

## Next Steps

- Sign up for [Hindsight Cloud](https://hindsight.vectorize.io) if you want a hosted backend
- Read the [full Hindsight docs](https://hindsight.vectorize.io/docs)
- Follow the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart)
- Review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall)
- Review [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain)
- Compare multi-tool workflows in [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents)
