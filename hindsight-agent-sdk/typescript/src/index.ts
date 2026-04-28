/**
 * Hindsight Agent SDK — self-learning knowledge pages for AI agents.
 *
 * Opinionated wrapper over the Hindsight client for managing wiki pages.
 * Designed to be embedded in harness plugins (OpenClaw, Hermes, Claude Code, etc.).
 *
 * Usage:
 *   import { AgentWiki } from "@vectorize-io/hindsight-agent-sdk";
 *   const wiki = new AgentWiki({ apiUrl: "http://localhost:8888", bankId: "my-bank" });
 *   const pages = await wiki.listPages();
 */

export interface AgentWikiConfig {
  apiUrl: string;
  bankId: string;
  apiToken?: string;
}

export interface ToolSchema {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

// Opinionated defaults for wiki pages
const WIKI_TRIGGER = {
  mode: "delta",
  refresh_after_consolidation: true,
  exclude_mental_models: true,
  fact_types: ["observation"],
} as const;

export class AgentWiki {
  private readonly apiUrl: string;
  private readonly bankId: string;
  private readonly headers: Record<string, string>;

  constructor(config: AgentWikiConfig) {
    this.apiUrl = config.apiUrl.replace(/\/$/, "");
    this.bankId = config.bankId;
    this.headers = { "Content-Type": "application/json" };
    if (config.apiToken) {
      this.headers["Authorization"] = `Bearer ${config.apiToken}`;
    }
  }

  private bankUrl(path: string): string {
    return `${this.apiUrl}/v1/default/banks/${this.bankId}${path}`;
  }

  private async request(method: string, url: string, body?: unknown): Promise<unknown> {
    const options: RequestInit = { method, headers: this.headers };
    if (body) {
      options.body = JSON.stringify(body);
    }
    const resp = await fetch(url, options);
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status}: ${text}`);
    }
    return resp.json();
  }

  // ── Pages ────────────────────────────────────────────

  async listPages(): Promise<unknown> {
    return this.request("GET", this.bankUrl("/mental-models"));
  }

  async getPage(pageId: string): Promise<unknown> {
    return this.request("GET", this.bankUrl(`/mental-models/${pageId}`));
  }

  async createPage(
    pageId: string,
    name: string,
    sourceQuery: string,
    maxTokens = 4096,
  ): Promise<unknown> {
    return this.request("POST", this.bankUrl("/mental-models"), {
      id: pageId,
      name,
      source_query: sourceQuery,
      max_tokens: maxTokens,
      trigger: WIKI_TRIGGER,
    });
  }

  async updatePage(
    pageId: string,
    updates: { name?: string; sourceQuery?: string },
  ): Promise<unknown> {
    const body: Record<string, string> = {};
    if (updates.name) body.name = updates.name;
    if (updates.sourceQuery) body.source_query = updates.sourceQuery;
    return this.request("PATCH", this.bankUrl(`/mental-models/${pageId}`), body);
  }

  async deletePage(pageId: string): Promise<void> {
    await this.request("DELETE", this.bankUrl(`/mental-models/${pageId}`));
  }

  // ── Recall ───────────────────────────────────────────

  async recall(query: string, maxResults = 10): Promise<unknown> {
    return this.request("POST", this.bankUrl("/memories/recall"), {
      query,
      max_results: maxResults,
    });
  }

  // ── Ingest ───────────────────────────────────────────

  async ingest(title: string, content: string): Promise<unknown> {
    const docId = title.toLowerCase().replace(/ /g, "-");
    return this.request("POST", this.bankUrl("/memories"), {
      items: [{ content, document_id: docId }],
      async: true,
    });
  }

  // ── Documents ────────────────────────────────────────

  async listDocuments(): Promise<unknown> {
    return this.request("GET", this.bankUrl("/documents"));
  }

  // ── Tool Schemas ─────────────────────────────────────

  static toolSchemas(): ToolSchema[] {
    return [
      {
        name: "hindsight_wiki_list",
        description: "List all knowledge pages. Returns page names, IDs, and content.",
        parameters: { type: "object", properties: {}, required: [] },
      },
      {
        name: "hindsight_wiki_get",
        description: "Get a specific knowledge page by ID.",
        parameters: {
          type: "object",
          properties: {
            page_id: { type: "string", description: "Page identifier" },
          },
          required: ["page_id"],
        },
      },
      {
        name: "hindsight_wiki_create",
        description:
          "Create a new knowledge page. The source_query is a question the system re-asks after every consolidation to rebuild the page.",
        parameters: {
          type: "object",
          properties: {
            page_id: {
              type: "string",
              description: "Page ID (lowercase with hyphens)",
            },
            name: { type: "string", description: "Human-readable page name" },
            source_query: {
              type: "string",
              description: "Synthesis query — the question that rebuilds this page",
            },
          },
          required: ["page_id", "name", "source_query"],
        },
      },
      {
        name: "hindsight_wiki_update",
        description: "Update a knowledge page's name or source query.",
        parameters: {
          type: "object",
          properties: {
            page_id: { type: "string", description: "Page identifier" },
            name: { type: "string", description: "New page name" },
            source_query: { type: "string", description: "New synthesis query" },
          },
          required: ["page_id"],
        },
      },
      {
        name: "hindsight_wiki_delete",
        description: "Delete a knowledge page.",
        parameters: {
          type: "object",
          properties: {
            page_id: { type: "string", description: "Page identifier" },
          },
          required: ["page_id"],
        },
      },
      {
        name: "hindsight_wiki_recall",
        description: "Search agent memories for specific facts, numbers, or details.",
        parameters: {
          type: "object",
          properties: {
            query: { type: "string", description: "Natural language search query" },
            max_results: {
              type: "integer",
              description: "Maximum results (default: 10)",
            },
          },
          required: ["query"],
        },
      },
      {
        name: "hindsight_wiki_ingest",
        description:
          "Upload a document into agent memory. Pass raw content — never summarize before ingesting.",
        parameters: {
          type: "object",
          properties: {
            title: { type: "string", description: "Document title (used as ID)" },
            content: { type: "string", description: "Document content" },
          },
          required: ["title", "content"],
        },
      },
    ];
  }

  /**
   * Dispatch a tool call. Plugins can use this as a unified handler.
   */
  async handleToolCall(
    toolName: string,
    args: Record<string, unknown>,
  ): Promise<string> {
    try {
      switch (toolName) {
        case "hindsight_wiki_list":
          return JSON.stringify(await this.listPages());
        case "hindsight_wiki_get":
          return JSON.stringify(await this.getPage(args.page_id as string));
        case "hindsight_wiki_create":
          return JSON.stringify(
            await this.createPage(
              args.page_id as string,
              args.name as string,
              args.source_query as string,
            ),
          );
        case "hindsight_wiki_update":
          return JSON.stringify(
            await this.updatePage(args.page_id as string, {
              name: args.name as string | undefined,
              sourceQuery: args.source_query as string | undefined,
            }),
          );
        case "hindsight_wiki_delete":
          await this.deletePage(args.page_id as string);
          return JSON.stringify({ success: true });
        case "hindsight_wiki_recall":
          return JSON.stringify(
            await this.recall(
              args.query as string,
              (args.max_results as number) ?? 10,
            ),
          );
        case "hindsight_wiki_ingest":
          return JSON.stringify(
            await this.ingest(args.title as string, args.content as string),
          );
        default:
          return JSON.stringify({ error: `Unknown tool: ${toolName}` });
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      return JSON.stringify({ error: message });
    }
  }
}
