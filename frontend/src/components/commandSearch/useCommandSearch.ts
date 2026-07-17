import { useCallback, useMemo, type ElementType } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Database,
  MessageSquare,
  Server,
  UserRoundCog,
  Users,
  Webhook,
} from "lucide-react";

import { usePermissions } from "@/context/PermissionContext";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { getAgentConfigsList, getKnowledgeItemsList } from "@/services/api";
import { fetchOperators } from "@/services/operators";
import { getAllDataSources } from "@/services/dataSources";
import { getAllMCPServers } from "@/services/mcpServer";
import { getAllWebhooks } from "@/services/webhook";
import { fetchTranscripts } from "@/services/transcripts";

const MAX_PER_GROUP = 6;
const MIN_QUERY_LEN = 2;

// A conversation's "#" is a fragment of its id; only search conversations when
// the token looks like an id fragment (hex/dashes), never by topic.
const CONVERSATION_ID_RE = /^[0-9a-f-]{2,}$/i;

export type CommandResultItem = {
  /** Unique cmdk identity — separate from `url` (list-nav rows can share a URL). */
  value: string;
  /** The matched value, e.g. an agent name or "Chat #97ee". */
  title: string;
  /** Navigation target. */
  url: string;
};

export type CommandResultGroup = {
  key: string;
  /** Section heading — the page the items live in (e.g. "Agent Studio"). */
  page: string;
  icon: ElementType;
  items: CommandResultItem[];
};

type NormalizedRow = { id: string; title: string };

// Entities whose lists have no server-side text search — fetched once per
// palette-open and filtered in the browser.
type IndexEntity = {
  key: string;
  page: string;
  icon: ElementType;
  permissions: string[];
  load: () => Promise<NormalizedRow[]>;
  buildUrl: (row: NormalizedRow) => string;
};

const INDEX_ENTITIES: IndexEntity[] = [
  {
    key: "agents",
    page: "Agent Studio",
    icon: UserRoundCog,
    permissions: ["read:llm_analyst"],
    load: async () => {
      const res = await getAgentConfigsList(1, 100);
      return (res?.items ?? []).map((a) => ({ id: a.id, title: a.name }));
    },
    buildUrl: (row) => `/ai-agents/workflow/${row.id}`,
  },
  {
    key: "knowledge",
    page: "Knowledge Base",
    icon: BookOpen,
    permissions: ["*", "update:knowledge_base"],
    load: async () => {
      const res = await getKnowledgeItemsList(1, 100);
      return (res?.items ?? []).map((k) => ({ id: k.id, title: k.name }));
    },
    buildUrl: (row) => `/knowledge-base/edit/${row.id}`,
  },
  {
    key: "operators",
    page: "Operators",
    icon: Users,
    permissions: ["read:operator"],
    load: async () => {
      const ops = await fetchOperators();
      return ops
        .filter((o) => Boolean(o.id))
        .map((o) => ({
          id: o.id as string,
          title: `${o.firstName ?? ""} ${o.lastName ?? ""}`.trim(),
        }));
    },
    // Deep link into the operator's profile (opened by the Operators page).
    buildUrl: (row) => `/operators?operator=${encodeURIComponent(row.id)}`,
  },
  {
    key: "dataSources",
    page: "Data Sources",
    icon: Database,
    permissions: ["read:data_source"],
    load: async () => {
      const sources = await getAllDataSources();
      return (sources ?? [])
        .filter((d) => Boolean(d.id))
        .map((d) => ({ id: d.id as string, title: d.name }));
    },
    buildUrl: () => "/data-sources",
  },
  {
    key: "mcpServers",
    page: "MCP Servers",
    icon: Server,
    permissions: ["read:mcp_server"],
    load: async () => {
      const servers = await getAllMCPServers();
      return (servers ?? []).map((s) => ({ id: s.id, title: s.name }));
    },
    buildUrl: () => "/mcp-servers",
  },
  {
    key: "webhooks",
    page: "Webhooks",
    icon: Webhook,
    permissions: ["read:webhook"],
    load: async () => {
      const hooks = await getAllWebhooks();
      return (hooks ?? []).map((h) => ({ id: h.id, title: h.name }));
    },
    buildUrl: () => "/webhooks",
  },
];

function conversationToken(raw: string): string {
  return raw.replace(/^#/, "").trim();
}

// Conversations: server-side lookup by id fragment only (the "#"), not topic.
async function searchConversations(raw: string): Promise<CommandResultItem[]> {
  const res = await fetchTranscripts({
    id_suffix: conversationToken(raw),
    limit: MAX_PER_GROUP,
  });
  return (res.items ?? []).map((c) => ({
    value: `conversation:${c.id}`,
    title: `Chat #${c.id.slice(-4)}`,
    url: `/transcripts?conversation=${encodeURIComponent(c.id)}`,
  }));
}

/**
 * Fans out to the per-entity list services (permission-gated), filters the
 * cached results by the debounced query, and returns results grouped by page
 * (heading + items, like the sidebar). Conversations are searched server-side
 * by their "#" id fragment. Only runs while the palette is `open`.
 */
export function useCommandSearch(query: string, open: boolean) {
  const permissions = usePermissions();
  const hasAny = useCallback(
    (required: string[]) =>
      required.length === 0 ||
      permissions.includes("*") ||
      required.some((p) => permissions.includes(p)),
    [permissions],
  );

  const liveQuery = query.trim();
  const debounced = useDebouncedValue(liveQuery, 150);
  const q = debounced.toLowerCase();
  const activeLive = open && liveQuery.length >= MIN_QUERY_LEN;
  const activeSettled = open && debounced.length >= MIN_QUERY_LEN;

  // Index lists — one query per entity, cached for the session, gated by permission.
  const indexQueries = useQueries({
    queries: INDEX_ENTITIES.map((entity) => ({
      queryKey: ["command-index", entity.key],
      queryFn: entity.load,
      enabled: open && hasAny(entity.permissions),
      staleTime: 5 * 60 * 1000,
    })),
  });

  const convToken = conversationToken(debounced);
  const canConversations = hasAny(["read:conversation"]);
  const conversationsEnabled =
    activeSettled && canConversations && CONVERSATION_ID_RE.test(convToken);
  const conversationsQuery = useQuery({
    queryKey: ["command-conversations", convToken],
    queryFn: () => searchConversations(debounced),
    enabled: conversationsEnabled,
    staleTime: 30 * 1000,
  });

  const groups = useMemo<CommandResultGroup[]>(() => {
    if (!activeSettled) return [];
    const out: CommandResultGroup[] = [];

    INDEX_ENTITIES.forEach((entity, i) => {
      const rows = (indexQueries[i]?.data ?? []) as NormalizedRow[];
      const items = rows
        .filter((r) => r.title.toLowerCase().includes(q))
        .slice(0, MAX_PER_GROUP)
        .map((r) => ({
          value: `${entity.key}:${r.id}`,
          title: r.title,
          url: entity.buildUrl(r),
        }));
      if (items.length > 0) {
        out.push({ key: entity.key, page: entity.page, icon: entity.icon, items });
      }
    });

    const conversations = conversationsQuery.data ?? [];
    if (conversations.length > 0) {
      out.push({ key: "conversations", page: "Conversations", icon: MessageSquare, items: conversations });
    }

    return out;
  }, [activeSettled, q, indexQueries, conversationsQuery.data]);

  // "Searching" covers the debounce gap and any in-flight fetch, so the empty
  // state never flashes before results settle.
  const loading =
    activeLive &&
    (liveQuery !== debounced ||
      (conversationsEnabled && conversationsQuery.isFetching) ||
      indexQueries.some((res) => res.isFetching));

  return { groups, loading };
}
