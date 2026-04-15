---
title: "Guide: Add Persistent Memory to AG2 with Hindsight"
authors: [benfrank241]
date: 2026-04-15
tags: [how-to, ag2, agents, memory]
description: "Add persistent memory to AG2 with Hindsight using retain, recall, and reflect tools, then verify shared memory works across separate conversations."
image: /img/blog/guide-ag2-persistent-memory-with-hindsight.png
hide_table_of_contents: true
---

![Guide: Add Persistent Memory to AG2 with Hindsight](/img/blog/guide-ag2-persistent-memory-with-hindsight.png)

If you want **persistent memory in AG2 with Hindsight**, the core move is simple: register Hindsight's retain, recall, and reflect tools on your AG2 agents and point them at a bank that survives beyond a single run. From there, AG2 agents can store useful facts, retrieve prior context, and reason over what they have learned across separate conversations.

This is valuable because AG2 does not magically accumulate long-term knowledge on its own. It can carry chat state within a run, but durable cross-run memory needs a backend. Hindsight gives AG2 that backend without forcing you to build your own extraction, retrieval, or memory routing layer.

This guide shows the cleanest AG2 setup, how the tools map onto AG2's registration model, how to use a shared bank for multi-agent workflows, and how to verify the memory layer is actually working. Keep the [docs home](https://hindsight.vectorize.io/docs) and the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) nearby while you work.

<!-- truncate -->

> **Quick answer**
>
> 1. Install `hindsight-ag2`.
> 2. Create your AG2 agents as usual.
> 3. Call `register_hindsight_tools(...)` with a bank ID.
> 4. Let the agent use `hindsight_retain`, `hindsight_recall`, and `hindsight_reflect`.
> 5. Run two separate conversations and verify the second one can recall what the first one stored.

## Prerequisites

Before you start, make sure you have:

- Python 3.10 or newer
- AG2 installed and working
- A Hindsight server or Hindsight Cloud account
- A bank ID strategy for your users, team, or project

If you have not used Hindsight before, start with the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart) so the API and bank model are familiar before you wire them into AG2.

## Step 1: Install the integration

Install the package:

```bash
pip install hindsight-ag2
```

If you are running against Hindsight Cloud, keep your API key available. If you are using a local deployment, make sure the base URL is reachable from the AG2 process.

## Step 2: Create your AG2 agents normally

You do not need a custom AG2 fork or a special agent class. Start with the agents you were already going to use.

```python
from autogen import AssistantAgent, UserProxyAgent, LLMConfig
from hindsight_ag2 import register_hindsight_tools

llm_config = LLMConfig(api_type="openai", model="gpt-4o-mini")

with llm_config:
    assistant = AssistantAgent(
        name="assistant",
        system_message="You are a helpful assistant with long-term memory.",
    )
    user_proxy = UserProxyAgent(
        name="user",
        human_input_mode="NEVER",
    )
```

At this point the agent is still stateless across runs. The memory layer appears in the next step.

## Step 3: Register Hindsight tools

Now register the memory tools on the agents:

```python
register_hindsight_tools(
    assistant,
    user_proxy,
    bank_id="my-bank",
    hindsight_api_url="http://localhost:8888",
)
```

That gives the assistant three AG2-compatible tools backed by Hindsight:

- `hindsight_retain`
- `hindsight_recall`
- `hindsight_reflect`

These are plain Python functions with type hints that fit AG2's registration model. In other words, the integration feels native to AG2 rather than bolted on from the outside.

## Step 4: Understand what each tool is for

### `hindsight_retain`

Use this when the agent learns something that should still matter later.

Examples:

- user preferences
- system constraints
- architectural decisions
- recurring failure modes

### `hindsight_recall`

Use this when the agent needs to search for prior context relevant to the current task.

Examples:

- prior environment decisions
- earlier bug reports
- stored user preferences
- facts from an earlier planning session

### `hindsight_reflect`

Use this when the agent needs a synthesized answer based on multiple memories rather than a raw list of recalled facts.

Examples:

- “What do we know about this user's stack?”
- “What are the main issues this team keeps running into?”
- “What architecture direction fits the decisions we made before?”

For the lower-level API behavior, read [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain) and [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall).

## Step 5: Verify cross-conversation memory

Run one conversation that stores a fact:

```python
result = user_proxy.initiate_chat(
    assistant,
    message="Remember that I prefer Python over JavaScript for internal tools.",
)
```

Then run a second conversation and ask for the remembered preference:

```python
result = user_proxy.initiate_chat(
    assistant,
    message="What do you know about my language preference for internal tools?",
)
```

If the setup is correct, the second run should be able to recall what the first run stored.

That is the practical success test. If every new run starts from nothing, the memory layer is not wired correctly yet.

## Shared memory for multi-agent workflows

One of the more useful AG2 patterns is shared memory across several agents in the same workflow.

Example:

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager, LLMConfig
from hindsight_ag2 import register_hindsight_tools

llm_config = LLMConfig(api_type="openai", model="gpt-4o-mini")

with llm_config:
    researcher = AssistantAgent(name="researcher", system_message="You research topics.")
    writer = AssistantAgent(name="writer", system_message="You write content.")
    executor = UserProxyAgent(name="executor", human_input_mode="NEVER")

for agent in [researcher, writer]:
    register_hindsight_tools(agent, executor, bank_id="team-memory")

group_chat = GroupChat(agents=[researcher, writer, executor], messages=[])
manager = GroupChatManager(groupchat=group_chat)
```

With this pattern, one agent can store a useful fact and another agent can benefit from it later, as long as they share the same bank.

This is the same broad idea behind [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents), applied to AG2's multi-agent model.

## Configuration tips that matter in production

### Choose bank IDs deliberately

A good bank ID strategy matters more than most people expect. Common options are:

- one bank per user
- one bank per project
- one bank per team workflow

### Use tags when the workflow has several sources

Tags make it easier to filter what gets retained and what gets recalled later.

### Start with a mid budget

The default recall and reflect budget is usually the right starting point. Raise it only if you know you need deeper search or synthesis.

### Keep the agent prompt honest about memory

Tell the agent it has memory tools and when it should use them. Do not imply it already knows everything unless it actually recalled the information.

## Troubleshooting

### The tools register, but the agent never seems to remember anything

Verify that the agent is actually calling the retain tool, not just answering conversationally.

### Recall returns nothing right after a retain call

Retain is asynchronous in the overall pipeline. Wait a few seconds and try recall again.

### Multi-agent memory is inconsistent

Make sure every agent that should share memory is using the same bank ID.

### Local development works, but production does not

Double-check your Hindsight base URL, auth, and bank routing assumptions.

## FAQ

### Is AG2 the same as AutoGen here?

They are related, but AG2 has its own package and integration surface. Use the AG2 integration for AG2 projects.

### Can I use this with GroupChat?

Yes. Shared-bank GroupChat workflows are one of the best use cases.

### Do I need Hindsight Cloud?

No. You can use a local or self-hosted Hindsight deployment too.

### Can I expose only some memory tools?

Yes. The integration supports selective inclusion if you do not want every tool available.

## Next Steps

- Sign up for [Hindsight Cloud](https://hindsight.vectorize.io) if you want a hosted memory backend
- Read the [full Hindsight docs](https://hindsight.vectorize.io/docs)
- Follow the [quickstart guide](https://hindsight.vectorize.io/docs/quickstart)
- Review [Hindsight's recall API](https://hindsight.vectorize.io/docs/api/recall)
- Review [Hindsight's retain API](https://hindsight.vectorize.io/docs/api/retain)
- Compare shared-bank workflows in [Team Shared Memory for AI Coding Agents](https://hindsight.vectorize.io/blog/team-shared-memory-ai-coding-agents)
