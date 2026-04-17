# Self-Improving Agent Skills: Findings

Research log from building and testing file-based procedural memory for OpenClaw agents (April 2026). Goal: understand where local file-based memory breaks and where an external system (like Hindsight) is genuinely needed — not assumed.

## Context

We built an `agent-memory` skill that gives an OpenClaw agent a `~/.agent-memory/<agent>/` directory where it maintains a wiki of everything it learned. Two file types: **knowledge files** (current-state, in-place updates) and **activity logs** (append-only, what was delivered). All files have mandatory evidence sections. Directory is git-tracked for version history.

Tested primarily with a "news-feed" agent that curates AI/ML news for the user.

Related work: [Memento-Skills (arXiv:2603.18743)](https://arxiv.org/abs/2603.18743) — "Let Agents Design Agents". Similar premise (skills as memory, read-write reflective learning), but their skills are executable code folders mutated by a judge, not wiki-style knowledge files.

---

## Architecture Options Tested

### Option A: Agent writes its own memory (synchronous, in-session)

The agent reads memory files at the start of each turn, does the task, then writes/updates memory files after responding.

**Setup:**
- Skill instructs the agent on file structure, naming, evidence format
- Two mandatory triggers: (1) knowledge updates when something durable is learned, (2) activity log entry after every task run
- Write order: respond → repair structural issues → update files → git commit
- Mandatory end-of-turn checklist to catch missed writes

**What worked:**
- Agent reads memory reliably and uses it to inform decisions (dedup, preferences, procedures)
- Activity log queries work well ("what Vercel items did you show me?")
- Evidence trail provides basic provenance
- Git history gives full diffs and rollback
- Index file (`_index.md`) helps with retrieval at moderate scale
- Agent's self-diagnosis of skill ambiguities was excellent — it identified gaps we hadn't seen

**What broke:**
1. **Unreliable execution of post-response writes.** The agent understood the write rules, agreed with them, then forgot to execute step 3/4 after generating the response. The LLM's natural stopping point is after the visible output — post-scripts get dropped. The checklist (`📝 Memory: [wrote: X | logged: Y | committed: Z]`) helps but is a band-aid: it catches the failure, doesn't prevent it.

2. **Latency.** Every turn pays 2-4 extra tool calls for memory I/O (read index, read relevant files, write updates, git commit). ~2-8 seconds of overhead the user can feel.

3. **Agent asks user about memory structure.** Without explicit instruction not to, the agent proposes file organization decisions to the user ("should I create a vercel-items.md?"). Memory should be internal — the user shouldn't know or care how it's organized. Required adding rule 11: "never surface memory structure to the user."

4. **Duplicate files.** Agent created `preferences.md` AND `news-feed-preferences.md` for the same topic. Required explicit dedup rules and immediate merge-on-discovery.

5. **Missing structural scaffolding.** Agent discovered `_index.md` was missing, noted it, but didn't fix it in the same turn. Required making repair mandatory in the same turn, not deferred.

6. **No cross-session pattern detection.** The agent only sees what it reads from files. If the user rejected hardware benchmarks across 4 separate sessions but the agent didn't read the right file each time, the pattern goes unnoticed. Each session is stateless except for explicit file reads.

**Fundamental limitation:** The agent is both the worker AND the memory system. When it's busy generating a complex response (10-item news feed with web searches), the "also update your notes" instruction competes for attention with the primary task. The primary task wins.

### Option B: Background LLM process (asynchronous, offline)

Not fully implemented, but designed. A separate script reads session transcripts from OpenClaw's JSONL files after each session, calls an LLM to extract what's wiki-worthy, updates the memory files, and commits.

**Why B is better in theory:**
- **Reliability:** A script that runs as a cron/hook doesn't forget steps. It always processes every turn.
- **No latency cost:** The user's turn isn't blocked by memory writes.
- **Full context:** The script sees the complete session transcript, not just the current turn. Can detect patterns across the session.
- **Batching:** Can process multiple turns at once, dedup, resolve contradictions in one pass.
- **Separation of concerns:** The agent does the task; the script maintains memory. Neither interferes with the other.

**Why B is hard without an external system:**
- **Cron/hook infrastructure is painful.** Setting up a reliable post-session hook that survives machine restarts, handles errors, retries on failure — that's a system, not a script. "Just run a cron job" is easy to say, hard to maintain.
- **LLM cost and coordination.** The script needs its own LLM call budget. If it uses the same model as the agent, you're doubling LLM cost. If it uses a cheaper model, synthesis quality drops.
- **Checkpoint management.** The script needs to track "which turns have I already processed" to avoid re-processing. That's a checkpoint file that can get out of sync.
- **File locking.** The agent might be reading memory files while the script is writing them. Race conditions on the wiki.
- **No semantic search.** Even with B, retrieving from 50+ memory files requires the agent to read the index and guess which files are relevant. No embeddings, no similarity search.

### Option C: Mechanical extraction (no LLM, regex/heuristic)

Designed but rejected for knowledge extraction. Works for activity logging (parse session transcript → extract delivered items → append to log) but can't extract preferences, rules, or procedures from natural language without LLM judgment.

**Verdict:** C is a valid sub-component of B (for the activity-log part specifically), not a standalone solution.

---

## Key Findings

### 1. Capture and synthesis must be separated

Asking the agent to both produce output AND maintain its memory in the same turn is unreliable. The capture (raw logging) must be infrastructure-level and deterministic. The synthesis (extracting knowledge from raw logs) can be LLM-driven but should happen asynchronously.

This is the single most important finding. It's also exactly what Hindsight's architecture does: auto-retain (deterministic hook) + consolidation (async LLM synthesis).

### 2. The agent is an excellent reader but an unreliable writer

Reading memory files and applying them to the task works well. The agent correctly deduplicates, applies preferences, follows procedures from memory. The failure is consistently on the write side — updating files after the task is done. Reads are pre-task (motivated by the task); writes are post-task (afterthought).

### 3. Evidence/provenance is valuable but expensive

The evidence trail (every fact cites a dated event) is useful for debugging "why does the agent think X". Git history adds full diffs. But maintaining evidence is another post-response write the agent can forget, and it adds ~30% more content to every file update.

### 4. File-based retrieval has a scale ceiling

With an index file, the agent can efficiently work with ~20-30 memory files. Beyond that, it needs to read the index, make relevance judgments, and selectively read — which adds latency and can miss relevant files. Embedding-based search (what Hindsight provides) removes this ceiling.

### 5. Memento-Skills' approach (skill = memory, agent mutates it) has the same write-reliability problem

Their Read-Write loop has the same structure: the agent acts, then reflects and rewrites the skill. They gate writes with a judge + unit tests + rollback — much heavier infrastructure than our evidence-and-commit approach, but it exists because the same failure mode (agent forgets/botches the write) exists for them too. Their solution: make the write a separate, guarded pipeline. Ours: post-response checklist. Theirs is more reliable but much more complex.

### 6. An external system's irreducible value is reliable capture + async synthesis

After testing all options, the value an external system (Hindsight, or anything like it) provides over files is:

| Capability | Files | External system |
|---|---|---|
| Reliable capture (never misses a turn) | ❌ Agent forgets | ✅ Hook-driven, deterministic |
| Async synthesis (no user-facing latency) | ❌ Blocks the turn | ✅ Background worker |
| Semantic search at scale | ❌ Index + grep | ✅ Embeddings + reranking |
| Cross-session pattern detection | ❌ Agent only sees what it reads | ✅ Sees all retained facts |
| Contradiction resolution | ❌ Agent must notice + fix | ✅ Consolidation pipeline |
| Provenance chain | ⚠️ Evidence section (manual) | ⚠️ Possible but not built yet |

What an external system does NOT provide better than files:
- **Transparency:** Files are more readable than a database
- **Simplicity:** Zero infrastructure for files
- **Agent autonomy:** The agent decides what matters in both cases
- **Offline/no-server:** Files work without any running service

### 7. The hybrid is probably the right answer

- **Files** for the agent's curated wiki (knowledge files, readable, transparent, git-tracked)
- **External system** for reliable capture (never miss a turn) + async synthesis (background LLM updates the wiki from captured turns) + semantic search (retrieve from the wiki at scale)

The file wiki becomes the *rendered output* of the external system's synthesis, not a competing artifact. The agent reads files; the system writes them. The agent can *also* write (for in-session corrections that can't wait for async), but the system is the primary writer.

---

## Requirements: What the External System Actually Needs

The file-based experiment revealed that the external system isn't just "Hindsight as-is with a hook". The system needs to present knowledge the way the agent naturally wants to consume it — as a navigable, topic-organized structure, not a flat bag of facts.

### The core problem Hindsight doesn't solve today

Hindsight stores facts (world/experience/observation) in a flat bank. Recall does semantic search over them. Mental models synthesize a text blob from a source_query. None of these give the agent what the file-based wiki gave naturally: **a browsable topic structure where each topic is a self-contained briefing with provenance**.

The agent doesn't want to ask "recall everything about news preferences". It wants to open the "preferences" page, read it, and act. The system needs to support that navigation pattern.

### Required capabilities

**1. Topic-based organization (file-system-like interface)**

The system must let the agent (or a synthesis process) organize knowledge into named topics — like files in a directory:

```
bank/
  preferences          → current feed preferences + evidence
  source-list          → allowed/blocked sources + evidence
  rss-procedure        → how to fetch feeds reliably
  user-setup           → user's local config details
  feed-log             → activity history (append-only)
```

Each topic is a first-class entity with: id/name, content (structured text), provenance (which observations produced each statement), created_at, updated_at.

Not a flat list of 10,000 facts. Not a single mental-model blob. A navigable directory of topics the agent can `ls` and selectively `cat`.

**2. The system creates and maintains topics, not the agent**

After each session, the system:
- Reads the new session transcript
- Decides which existing topics need updating and whether new topics should be created
- Updates topic content with surgical changes (delta, not full rewrite)
- Tracks provenance: every statement in a topic links back to the observation(s) that produced it
- Handles contradiction resolution (newer wins, older marked superseded)
- Handles topic splitting (when a topic grows too large) and merging (when two topics overlap)

The agent NEVER writes to the topic store. It only reads. This eliminates the write-reliability problem entirely.

**3. Activity logging is a built-in concern, not agent-driven**

The system automatically maintains activity logs from session transcripts. For each completed task run detected in a transcript:
- What was requested
- What was delivered (extracted from assistant output)
- Sources used
- User reaction (if any)

The agent reads the activity log as another topic. It doesn't write it.

**4. Navigable interface for the agent**

The agent needs these operations at runtime:
- `list_topics()` → returns topic names + one-line descriptions (like `_index.md`)
- `read_topic(name)` → returns the current content of that topic
- `read_topic(name, with_provenance=true)` → returns content + which observations back each statement
- `search_topics(query)` → semantic search across all topic content (for when the agent doesn't know which topic to read)

These map cleanly to CLI commands or MCP tools:
```bash
hindsight topics list <bank>
hindsight topics read <bank> <topic>
hindsight topics search <bank> "query"
```

**5. Provenance is structural, not textual**

In the file-based approach, provenance is an `## Evidence` section the agent writes manually — unreliable and expensive. In the external system, provenance is a first-class data relationship:

```
topic_statement {
  text: "Item cap: 10 per run"
  sources: [observation_id_1, observation_id_2]
  first_stated: 2026-04-15
  last_reinforced: 2026-04-17
  confidence: high (3 supporting observations)
  status: active
}
```

Every statement traces to the observations that produced it. The agent can ask "why do you think the cap is 10?" and get back the actual user quotes. No manual evidence section needed.

**6. Cross-agent topic sharing**

Some topics are agent-specific (news-feed preferences). Others should be shared across agents (user voice, user timezone, known tools). The system needs:
- Per-agent topic namespaces (default)
- Shared/global topics that any agent can read
- No agent can write to another agent's namespace (the system does the cross-pollination if needed)

**7. Async processing with bounded latency**

The synthesis runs after each session, not during. But the latency needs to be bounded:
- Activity logs: updated within seconds (mechanical extraction, no LLM)
- Knowledge topics: updated within minutes (LLM synthesis, can be batched)
- The agent should know when topics were last updated (`last_updated` timestamp on each topic) so it can decide whether to also scan recent raw session transcripts for very-recent-turn context

### How this maps to Hindsight's current primitives

| Required capability | Current Hindsight | Gap |
|---|---|---|
| Topic-based organization | Mental models (one per topic) | ✅ Close — MMs are named, per-bank, have content. But they're text blobs, not structured statements. |
| System creates/maintains topics | Consolidation + MM refresh | ⚠️ Partial — consolidation extracts observations, MM refresh synthesizes from source_query. But no topic auto-creation, no structural delta updates, no topic splitting/merging. |
| Activity logging | Auto-retain captures sessions | ❌ No structured activity log extraction. Raw session text is retained but not parsed into "what was delivered". |
| Navigable interface | `mental-model list/get` | ⚠️ Close — list + get work. No `search` across MM content. No one-line descriptions in list. |
| Structural provenance | Not implemented | ❌ MM content is a text blob. No per-statement source tracking. |
| Cross-agent sharing | Multi-bank, but isolated | ❌ No shared topics across banks. Would need a cross-bank reference mechanism. |
| Bounded async latency | Consolidation + `refresh_after_consolidation` | ⚠️ Works but latency is variable (depends on worker queue depth). No guaranteed SLA. Activity log extraction doesn't exist. |

### What would need to change in Hindsight

1. **Mental models → Topics**: rename/rebrand to make the navigation metaphor explicit. Each "topic" has structured content (list of statements with provenance), not a text blob. Rendered to text for agent consumption, but stored as cited fragments internally.

2. **Auto-topic-creation**: the consolidation pipeline should detect when observations don't fit any existing topic and propose a new one. Currently MMs are user-created; topics should emerge from the data.

3. **Activity log as a built-in topic type**: a special topic that's populated mechanically from retained session transcripts — no LLM needed for "what was delivered", just structured extraction from the assistant's output.

4. **Delta updates with provenance**: each topic update is a patch (add statement X citing observations [a,b], supersede statement Y), not a full rewrite. The current MM delta mode work is heading here.

5. **Topic search**: semantic search across topic content, not just fact recall. "Which topic talks about RSS?" → returns the topic name, not 10 raw facts.

6. **Shared topic namespace**: a "global" or "shared" bank that all per-agent banks can read from. Populated by cross-bank observation analysis.

## Hindsight Feature Proposal: Knowledge Base (KB)

### Naming

- **Knowledge Base (KB)**: a named collection of related mental models within a bank, maintained by a shared mission/policy. Multiple KBs per bank. Each KB auto-manages its MMs from tagged observations.
- **Mental Model**: unchanged — one synthesized page within a KB (or standalone).
- **Mount**: client-side file rendering of a KB's mental models so the agent can browse them as files.

### Data model

```
KnowledgeBase:
  id              text PK
  bank_id         text FK → banks
  name            text
  mission         text         # policy: what topics to maintain, when to create/split, structure conventions
  tags            text[]       # scopes which observations feed this KB
  auto_create     boolean      # create new MMs when observations don't fit existing ones
  split_threshold int          # max statements per MM before proposing a split
  created_at      timestamptz
  updated_at      timestamptz
```

Mental models gain: `kb_id text FK → knowledge_bases (nullable)`. Null = standalone MM (backward-compatible).

### Pipeline (server-side, after consolidation)

```
retain → extraction → observations (tagged via retain_tags or auto)
                          ↓
         consolidation produces new observations
                          ↓
         refresh_after_consolidation fires
                          ↓
         for each KB whose tags match new observations:
           1. KB mission + observation list + existing MM index → LLM routing call:
              "which MMs should receive which observations? any new MMs needed?"
           2. For each affected MM: delta-mode refresh scoped to routed observations
           3. If auto_create=true and LLM proposed new MMs: create them with initial content
           4. Update KB.updated_at
```

No new write path for observations. The KB layer sits between consolidation and MM refresh — it adds routing + auto-creation, then delegates to existing MM refresh (with the delta mode being built).

### API

```
POST   /v1/{tenant}/banks/{bank_id}/knowledge-bases                    # create KB
GET    /v1/{tenant}/banks/{bank_id}/knowledge-bases                    # list KBs
GET    /v1/{tenant}/banks/{bank_id}/knowledge-bases/{kb_id}            # get KB + its MM list
PATCH  /v1/{tenant}/banks/{bank_id}/knowledge-bases/{kb_id}            # update mission/tags/policy
DELETE /v1/{tenant}/banks/{bank_id}/knowledge-bases/{kb_id}            # delete KB (MMs stay as orphans or get deleted)
GET    /v1/{tenant}/banks/{bank_id}/mental-models?kb={kb_id}           # list MMs in a KB
```

### CLI

```
hindsight kb create <bank> <name> --mission "..." [--tags tag1,tag2] [--auto-create]
hindsight kb list <bank>
hindsight kb get <bank> <kb_id>
hindsight kb update <bank> <kb_id> --mission "..."
hindsight kb delete <bank> <kb_id>
hindsight mental-model list <bank> --kb <kb_id>
```

### Client-side mount

The harness plugin (or a standalone CLI tool) renders a KB's mental models as files:

```
~/.agent-knowledge/<bank>/<kb>/
  _index.md              # auto-generated: one line per MM with name + summary
  preferences.md         # MM "preferences" content rendered as markdown
  source-list.md         # MM "source-list" content
  feed-log.md            # MM "feed-log" content (activity log)
  ...
```

Sync modes:
- **Eager** (default): dump all MMs to disk at session start. Simple, slight startup cost.
- **Lazy**: first `ls` triggers sync, cached for the session.

The agent reads files with normal tools (Read, cat, ls). No new tools needed. The mount is a convenience layer — the agent can also call the API directly via CLI.

### Recall integration

Recall results gain `mental_model_ids: ["preferences", "source-list"]` when the matched observation was used to produce content in those MMs. The agent can:

1. `recall("RSS feeds")` → gets facts + which MMs contain related synthesized knowledge
2. Read those MMs for the full page

Recall = search. MM = read the synthesized page. Two complementary operations.

### Skill file (agent is read-only)

```markdown
---
name: agent-memory
description: Your knowledge is stored as files mounted from Hindsight.
  Browse ~/.agent-knowledge/<bank>/<kb>/ for preferences, procedures,
  activity history. You read; the system writes.
---

# Agent Memory

Browse your knowledge at `~/.agent-knowledge/<bank>/<kb>/`.

- `ls` to see available topics
- `cat` to read a topic
- Use `hindsight memory recall <bank> "<query>"` if you need to search

You never write to these files. The system updates them automatically
from your conversations.
```

The agent's only job is reading. All write reliability concerns eliminated.

---

## PoC Spec: LLM Wiki Maintainer (Hindsight-agnostic)

Standalone tool that maintains a structured wiki from conversation transcripts. No database, no server, no Hindsight dependency. Pure files + LLM calls. Designed to validate the pattern before deciding what to build into Hindsight.

Inspired by [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and our findings from the agent-memory skill experiment.

### Three layers

```
raw/                          # immutable conversation transcripts
  sessions/                   # JSONL session files (from OpenClaw, Claude Code, etc.)
  sources/                    # optional: articles, docs, notes the user drops in

wiki/                         # LLM-maintained, git-tracked
  _index.md                   # topic catalog with one-line summaries
  _log.md                     # chronological: what was ingested/updated/linted when
  topics/                     # one file per topic, interlinked
    preferences.md
    source-list.md
    rss-procedure.md
    ...
  activity/                   # append-only task-run logs
    feed-log.md
    sweep-log.md

schema.md                    # configuration: wiki conventions, topic templates,
                              # what to extract, how to organize, domain hints
```

### Three operations

**1. Ingest** — process new conversation transcript(s) into the wiki

```
llm-wiki ingest <session-file-or-dir>
```

- Reads new session transcript(s) since last checkpoint
- Calls LLM: "here's the transcript, here's the current wiki index, here's the schema — what topics need creating/updating?"
- LLM returns a structured list of file operations: create topic X, update topic Y (with diff), append to activity log Z
- Each file operation carries provenance: which transcript lines produced this update
- Applies the operations, updates `_index.md` and `_log.md`, git commits
- Checkpoint: records which transcripts have been processed

One ingest can touch many wiki pages (Karpathy's "10-15 files per source"). The LLM sees the full wiki index so it knows where things belong.

**2. Query** — answer a question using the wiki (optional, agent can also just read files)

```
llm-wiki query "what are my news feed preferences?"
```

- Reads `_index.md`, finds relevant topic files, reads them
- Synthesizes an answer with citations to topic pages
- Optionally: files the answer back as a new wiki page if it's a valuable synthesis

For the agent use case, this is optional — the agent can just `cat wiki/topics/preferences.md` directly. But for human use (Karpathy's Obsidian model), the query interface is valuable.

**3. Lint** — health-check the wiki

```
llm-wiki lint
```

- Reads all topic files
- Calls LLM: check for contradictions, stale claims, duplicate topics, orphan pages (no inbound links), missing cross-references, overgrown files
- Produces a report + optional auto-fix (with git commit)
- Appends lint entry to `_log.md`

### Topic file format

```markdown
# Topic Name

<Current state of knowledge. Declarative, no hedging. Cross-references
to other topics use [[wiki-links]].>

See also: [[source-list]], [[rss-procedure]]

## Provenance

| Fact | Source | Date |
|---|---|---|
| Item cap is 10 | session 2026-04-15-abc123, turn 7: "I want 10 items" | 2026-04-15 |
| No academic papers | session 2026-04-15-abc123, turn 12: "no papers either" | 2026-04-15 |
| Window is 7 days | session 2026-04-16-def456, turn 3: "make it weekly" | 2026-04-16 |
```

Provenance is a structured table, not prose. Each fact maps to a specific transcript + turn + quote. This is the per-line provenance we discussed as Hindsight's potential differentiator — but implemented as plain markdown.

### Schema file

The schema tells the LLM how this particular wiki should work. Domain-specific. Examples:

```markdown
# Schema

## Domain
AI news feed agent. Topics typically cover: user preferences, source
lists, procedures, tool-specific knowledge, activity history.

## Conventions
- One topic per file, max ~50 lines before splitting
- Cross-reference with [[wiki-links]] when topics mention each other
- Activity logs are append-only, prune entries older than 30 days
- Provenance table is mandatory — no fact without a source citation

## Topic templates
- Knowledge topic: current state + provenance table + see-also links
- Activity log: dated entries with headlines, sources, user reaction

## Ingest instructions
- From conversations: extract preferences, corrections, decisions,
  procedures, reactions. Ignore ephemeral task chatter.
- From articles/sources: extract key claims, compare with existing
  topics, note contradictions.
```

### Implementation sketch

Python CLI. ~200-300 lines for v0.

```
llm-wiki/
  cli.py              # argparse: ingest, query, lint
  ingest.py            # read transcripts, call LLM, apply file ops
  query.py             # read index, find topics, synthesize answer
  lint.py              # health check
  llm.py               # LLM wrapper (OpenAI/Anthropic/local)
  checkpoint.py        # track processed transcripts
  schema.py            # load + validate schema.md
```

Dependencies: one LLM SDK (litellm or anthropic), nothing else. Git via subprocess.

### What this PoC validates

1. **Does the ingest → wiki pipeline produce better knowledge than the agent writing its own memory?** Compare wiki quality after 20 sessions (file-based agent-memory vs llm-wiki ingest from the same session transcripts).

2. **Does per-fact provenance actually work in practice?** Can the LLM consistently produce cited facts in a structured table, and can we trace any wiki statement back to the source transcript?

3. **How does cross-referencing emerge?** Does the LLM naturally create [[wiki-links]] between topics, and do they form a useful graph?

4. **What's the latency?** How fast is ingest for a typical 10-turn session? Is it fast enough to run after every session, or does it need batching?

5. **Where does pure-file-based break?** At what wiki size does `_index.md` stop being sufficient and you need search? How many topics before the LLM can't hold the full index in context?

6. **What would Hindsight add on top?** After running the PoC, the gaps should be clear: semantic search at scale, reliable capture hooks, concurrent write safety, cross-agent sharing. These become the Hindsight product requirements with real evidence, not assumptions.

## Open Questions

1. **Can the agent self-correct with just a checklist?** The `📝 Memory` checklist helps but it's unclear if it's reliable over 100+ sessions. Needs longer testing.

2. **What's the right latency for async synthesis?** If the wiki updates 5 minutes after the session, the next session might start before the update lands. Is that acceptable? Can the agent compensate by re-reading recent session transcripts directly?

3. **Provenance depth.** The evidence trail we built is agent-maintained (unreliable). Git gives diffs but not "this line came from turn X in session Y". A system with per-fact source tracking (the cited-fragments design we discussed) would be the real solution, but it's a significant data model change.

4. **Does the agent even need to write knowledge files, or just activity logs?** If the external system handles knowledge synthesis, the agent's only write responsibility is the activity log (what it delivered). That's the most mechanical part and the one most amenable to C-style extraction. The agent becomes read-only on knowledge, write-only on activity — simpler, more reliable.

5. **Cross-agent knowledge sharing.** Multiple agents (news-feed, discord-watch) would benefit from shared knowledge (user voice preferences, known sources). Files require manual symlinks or copies. A shared bank handles it automatically. Not tested yet.
