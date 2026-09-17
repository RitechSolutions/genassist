import {
  Home,
  Settings,
  LogOut,
  ChevronRight,
  ChevronsUpDown,
  LineChart,
  MessageSquare,
  UserRoundCog,
  Network,
  Waypoints,
  ListChecks,
  LifeBuoy,
  ScrollText,
  Users,
  UserRound,
  UsersRound,
  KeyRound,
  Contact,
  ShieldCheck,
  Search,
  LayoutGrid,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  useSidebar,
} from "@/components/sidebar";
import { useLocation } from "react-router";
import { Link } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import {
  logout,
  hasAnyPermission,
  getAuthMe,
  getTenantId,
} from "@/services/auth";
import toast from "react-hot-toast";
import { useEffect, useState, useCallback, useMemo } from "react";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import { FeatureFlags } from "@/config/featureFlags";
import { usePersistedState } from "@/hooks/usePersistedState";
import { cn } from "@/helpers/utils";
import { GenAssistLogo } from "@/components/GenAssistLogo";
import { NotificationBellPopover } from "@/components/NotificationBellPopover";
import { CommandSearchDialog } from "@/components/CommandSearchDialog";

// ---------------------------------------------------------------------------
// Types & data
// ---------------------------------------------------------------------------

export type BadgeTone = "new" | "beta" | "count";

export type MenuItem = {
  title: string;
  icon?: React.ElementType;
  url: string;
  permissionsRequired?: string[];
  children?: MenuItem[];
  feature_flag?: string;
  badge?: string;
  badgeTone?: BadgeTone;
};

export type NavGroup = {
  label: string;
  items: MenuItem[];
};

const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { title: "Dashboard", icon: Home, url: "/dashboard" },
      {
        title: "Agent Studio",
        icon: UserRoundCog,
        url: "/ai-agents",
        permissionsRequired: ["read:llm_analyst"],
      },
      {
        title: "Templates",
        icon: LayoutGrid,
        url: "/templates",
        permissionsRequired: ["*", "read:template"],
        feature_flag: FeatureFlags.FEATURE.TEMPLATE_MARKETPLACE,
        badge: "NEW",
        badgeTone: "new",
      },
      {
        title: "Conversations",
        icon: MessageSquare,
        url: "#",
        permissionsRequired: ["read:conversation"],
        children: [
          {
            title: "Conversations",
            url: "/transcripts",
            permissionsRequired: ["read:conversation"],
          },
          {
            title: "Reported Feedback",
            url: "/reported-feedback",
            permissionsRequired: ["read:conversation"],
          },
        ],
      },
      {
        title: "Analytics",
        icon: LineChart,
        url: "#",
        permissionsRequired: ["read:dashboard"],
        children: [
          {
            title: "AI Insights",
            url: "/analytics/ai-insights",
            permissionsRequired: ["read:dashboard"],
          },
          {
            title: "Agent Performance",
            url: "/analytics/agent-performance",
            permissionsRequired: ["read:dashboard"],
          },
          {
            title: "Node Analytics",
            url: "/analytics/node-analytics",
            permissionsRequired: ["read:dashboard"],
          },
          {
            title: "Cost Explorer",
            url: "/analytics/llm-usage",
            permissionsRequired: ["read:dashboard"],
            feature_flag: FeatureFlags.ANALYTICS.SHOW_COST_PER_CONVERSATION,
            badge: "NEW",
            badgeTone: "new",
          },
        ],
      },
      {
        title: "Operators",
        icon: Users,
        url: "/operators",
        permissionsRequired: ["read:operator"],
      },
    ],
  },
  {
    label: "Quality",
    items: [
      {
        title: "Tests",
        icon: ListChecks,
        url: "#",
        permissionsRequired: ["test:workflow"],
        badge: "BETA",
        badgeTone: "beta",
        children: [
          {
            title: "Datasets",
            url: "/tests/datasets",
            permissionsRequired: ["test:workflow"],
          },
          {
            title: "Evaluations",
            url: "/tests/evaluations",
            permissionsRequired: ["test:workflow"],
          },
          {
            title: "Evaluate ML models",
            url: "/tests/ml-model-evaluations",
            permissionsRequired: ["*", "read:ml_model"],
          },
        ],
      },
    ],
  },
  {
    label: "Connect",
    items: [
      {
        title: "Integrations",
        icon: Network,
        url: "#",
        children: [
          {
            title: "Knowledge Base",
            url: "/knowledge-base",
            permissionsRequired: ["*", "update:knowledge_base"],
          },
          {
            title: "ML Models",
            url: "/ml-models",
            permissionsRequired: ["*", "update:ml_model"],
          },
          {
            title: "Data Sources",
            url: "/data-sources",
            permissionsRequired: ["read:data_source"],
          },
          {
            title: "API Keys",
            url: "/api-keys",
            permissionsRequired: ["read:api_key"],
          },
          {
            title: "Webhooks",
            url: "/webhooks",
            permissionsRequired: ["read:webhook"],
          },
          {
            title: "MCP Servers",
            url: "/mcp-servers",
            permissionsRequired: ["read:mcp_server"],
          },
          {
            title: "Configuration Vars",
            url: "/app-settings",
            permissionsRequired: ["read:app_setting"],
          },
        ],
      },
      {
        title: "LLM Settings",
        icon: Waypoints,
        url: "#",
        children: [
          {
            title: "LLM Providers",
            url: "/llm-providers",
            permissionsRequired: ["read:llm_provider"],
          },
          {
            title: "Fallback Chains",
            url: "/fallback-chains",
            permissionsRequired: ["read:llm_provider"],
            feature_flag: FeatureFlags.LLM_SETTINGS.SHOW_FALLBACK_CHAINS,
          },
          {
            title: "Audio Providers",
            url: "/audio-providers",
            permissionsRequired: ["read:llm_provider"],
            feature_flag: FeatureFlags.LLM_SETTINGS.SHOW_AUDIO_PROVIDERS,
          },
          {
            title: "LLM Analyst",
            url: "/llm-analyst",
            permissionsRequired: ["read:llm_analyst"],
          },
          {
            title: "Fine Tune OpenAI",
            url: "/fine-tune",
            permissionsRequired: ["*", "read:openai_job"],
          },
          {
            title: "Local Fine-Tune",
            url: "/local-fine-tune",
            permissionsRequired: ["*", "read:local_fine_tuning"],
            feature_flag: FeatureFlags.LLM_SETTINGS.SHOW_LOCAL_FINE_TUNE,
          },
          {
            title: "Bedrock Fine-Tune",
            url: "/bedrock-fine-tune",
            permissionsRequired: ["*", "read:bedrock_job"],
            feature_flag: FeatureFlags.LLM_SETTINGS.SHOW_BEDROCK_FINE_TUNE,
          },
        ],
      },
    ],
  },
  {
    label: "Administration",
    items: [
      {
        title: "Users",
        icon: UserRound,
        url: "/users",
        permissionsRequired: ["read:user"],
      },
      {
        title: "Roles",
        icon: KeyRound,
        url: "/roles",
        permissionsRequired: ["read:role"],
      },
      {
        title: "User Types",
        icon: Contact,
        url: "/user-types",
        permissionsRequired: ["read:user_type"],
      },
      {
        title: "User Groups",
        icon: UsersRound,
        url: "/user-groups",
        permissionsRequired: ["read:user_group"],
      },
      {
        title: "GDPR Requests",
        icon: ShieldCheck,
        url: "/admin/gdpr-conversations",
        permissionsRequired: ["delete:conversation:gdpr"],
      },
      {
        title: "Audit Log",
        icon: ScrollText,
        url: "/audit-logs",
        permissionsRequired: ["read:audit_log"],
      },
    ],
  },
];

// Pinned to the bottom of the sidebar, above the user profile.
const footerItems: MenuItem[] = [
  { title: "Help Center", icon: LifeBuoy, url: "/help-center" },
  { title: "Settings", icon: Settings, url: "/settings" },
];

const STORAGE_KEYS = [
  "isConversationsOpen",
  "isAnalyticsOpen",
  "isTestsOpen",
  "isIntegrationOpen",
  "isLLMSettingsOpen",
  "isAdminOpen",
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isPathActive(currentPath: string, url: string): boolean {
  if (url === "#") return false;
  return currentPath === url || currentPath.startsWith(`${url}/`);
}

function hasActiveChild(item: MenuItem, currentPath: string): boolean {
  return (
    item.children?.some((child) => isPathActive(currentPath, child.url)) ??
    false
  );
}

// Filter a list of items to those matching a free-text query. A parent stays
// visible (with all children) when its own title matches, otherwise only its
// matching children are kept.
function filterBySearch(items: MenuItem[], query: string): MenuItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.reduce<MenuItem[]>((acc, item) => {
    const selfMatch = item.title.toLowerCase().includes(q);
    if (item.children) {
      const children = selfMatch
        ? item.children
        : item.children.filter((c) => c.title.toLowerCase().includes(q));
      if (selfMatch || children.length > 0) acc.push({ ...item, children });
    } else if (selfMatch) {
      acc.push(item);
    }
    return acc;
  }, []);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function NavBadge({
  label,
  tone = "beta",
  className,
}: {
  label: string;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold leading-none",
        tone === "new" &&
          "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400",
        tone === "beta" &&
          "bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400",
        tone === "count" &&
          "min-w-[18px] rounded-full bg-blue-600 px-1 text-center text-white",
        className
      )}
    >
      {label}
    </span>
  );
}

function NavLink({
  item,
  currentPath,
}: {
  item: MenuItem;
  currentPath: string;
}) {
  const active = isPathActive(currentPath, item.url);

  return (
    <Link
      to={item.url}
      className={cn(
        "group/link flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-sm font-medium transition-colors duration-150",
        active
          ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
          : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100"
      )}
    >
      {item.icon && (
        <item.icon
          className={cn(
            "h-4 w-4 shrink-0",
            active
              ? "text-zinc-700 dark:text-zinc-200"
              : "text-zinc-500 group-hover/link:text-zinc-600 dark:text-zinc-500 dark:group-hover/link:text-zinc-300"
          )}
          strokeWidth={2.25}
        />
      )}
      <span className="truncate">{item.title}</span>
      {item.badge && (
        <NavBadge label={item.badge} tone={item.badgeTone} className="ml-auto" />
      )}
    </Link>
  );
}

function CollapsibleMenuItem({
  item,
  currentPath,
  isOpen,
  onToggle,
}: {
  item: MenuItem;
  currentPath: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const childActive = hasActiveChild(item, currentPath);

  return (
    <div>
      <button
        onClick={onToggle}
        aria-expanded={isOpen}
        className={cn(
          "group/parent flex w-full items-center gap-2.5 rounded-md px-2.5 py-[7px] text-sm font-medium transition-colors duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-200 dark:focus-visible:ring-zinc-700",
          childActive
            ? "text-zinc-900 dark:text-zinc-50"
            : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100"
        )}
      >
        {item.icon && (
          <item.icon
            className={cn(
              "h-4 w-4 shrink-0",
              childActive
                ? "text-zinc-700 dark:text-zinc-200"
                : "text-zinc-500 group-hover/parent:text-zinc-600 dark:text-zinc-500 dark:group-hover/parent:text-zinc-300"
            )}
            strokeWidth={2.25}
          />
        )}
        <span className="truncate">{item.title}</span>
        {item.badge && <NavBadge label={item.badge} tone={item.badgeTone} />}
        <ChevronRight
          strokeWidth={2.25}
          className={cn(
            "ml-auto h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500 transition-transform duration-200",
            isOpen && "rotate-90"
          )}
        />
      </button>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-in-out",
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <div className="relative py-0.5 pl-[30px]">
            <div className="absolute bottom-0 left-[18px] top-0 w-px bg-zinc-200 dark:bg-zinc-700" />
            {item.children?.map((child, i) => {
              const active = isPathActive(currentPath, child.url);
              return (
                <Link
                  key={i}
                  to={child.url}
                  className={cn(
                    "flex items-center rounded-md px-2.5 py-[6px] text-sm transition-colors duration-150",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-200 dark:focus-visible:ring-zinc-700",
                    active
                      ? "bg-zinc-100 font-semibold text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
                      : "font-medium text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-200"
                  )}
                >
                  <span className="truncate">{child.title}</span>
                  {child.badge && (
                    <NavBadge
                      label={child.badge}
                      tone={child.badgeTone}
                      className="ml-auto"
                    />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function UserFooter({
  username,
  tenantId,
  onLogout,
}: {
  username: string;
  tenantId?: string;
  onLogout: () => void;
}) {
  const initials = username
    .split(/[\s._-]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join("");

  return (
    <div className="border-t border-zinc-100 dark:border-zinc-800 px-3 py-3">
      <div className="flex items-center gap-1.5">
        <div className="min-w-0 flex-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 transition-colors",
                  "hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-200 dark:hover:bg-zinc-800/60 dark:focus-visible:ring-zinc-700"
                )}
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-[11px] font-semibold text-zinc-600 dark:bg-zinc-700 dark:text-zinc-200">
                  {initials || "U"}
                </div>
                <div className="min-w-0 text-left">
                  <div className="truncate text-[13px] font-medium text-zinc-600 dark:text-zinc-300">
                    {username}
                  </div>
                  {tenantId ? (
                    <div className="truncate text-[11px] text-zinc-400 dark:text-zinc-500">
                      Tenant: <span className="font-medium">{tenantId}</span>
                    </div>
                  ) : null}
                </div>
                <ChevronsUpDown className="ml-auto h-3.5 w-3.5 text-zinc-300 dark:text-zinc-600" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-48">
              <DropdownMenuItem
                onClick={onLogout}
                className="flex items-center gap-2 text-red-600 dark:text-red-400"
              >
                <LogOut className="h-4 w-4" />
                <span>Logout</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AppSidebar() {
  const { isMobile, setOpenMobile } = useSidebar();
  const [username, setUsername] = useState<string>("");
  const [tenantId, setTenantId] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [commandOpen, setCommandOpen] = useState<boolean>(false);
  const { getFeatureItem } = useFeatureFlag();

  const location = useLocation();
  const currentPath = location.pathname;

  // Persisted collapsible state
  const [isConversationsOpen, toggleConversations, setConversationsOpen] =
    usePersistedState("isConversationsOpen", false);
  const [isAnalyticsOpen, toggleAnalytics, setAnalyticsOpen] =
    usePersistedState("isAnalyticsOpen", false);
  const [isTestsOpen, toggleTests, setTestsOpen] = usePersistedState(
    "isTestsOpen",
    false
  );
  const [isIntegrationsOpen, toggleIntegrations, setIntegrationsOpen] =
    usePersistedState("isIntegrationOpen", false);
  const [isLLMSettingsOpen, toggleLLMSettings, setLLMSettingsOpen] =
    usePersistedState("isLLMSettingsOpen", false);

  const toggleMap: Record<string, () => void> = useMemo(
    () => ({
      Conversations: toggleConversations,
      Analytics: toggleAnalytics,
      Tests: toggleTests,
      Integrations: toggleIntegrations,
      "LLM Settings": toggleLLMSettings,
    }),
    [
      toggleConversations,
      toggleAnalytics,
      toggleTests,
      toggleIntegrations,
      toggleLLMSettings,
    ]
  );

  const openMap: Record<string, boolean> = useMemo(
    () => ({
      Conversations: isConversationsOpen,
      Analytics: isAnalyticsOpen,
      Tests: isTestsOpen,
      Integrations: isIntegrationsOpen,
      "LLM Settings": isLLMSettingsOpen,
    }),
    [
      isConversationsOpen,
      isAnalyticsOpen,
      isTestsOpen,
      isIntegrationsOpen,
      isLLMSettingsOpen,
    ]
  );

  useEffect(() => {
    const cached = localStorage.getItem("auth_username");
    if (cached) {
      setUsername(cached);
      setTenantId(getTenantId() ?? "");
      return;
    }
    const loadUser = async () => {
      try {
        setTenantId(getTenantId() ?? "");
        const me = await getAuthMe();
        if (me?.username) {
          setUsername(me.username);
          localStorage.setItem("auth_username", me.username);
        }
      } catch {
        setUsername("");
        setTenantId(getTenantId() ?? "");
      }
    };
    loadUser();
  }, []);

  // Auto-expand section when navigating directly to a child route
  useEffect(() => {
    const setterMap: Record<string, (v: boolean) => void> = {
      Conversations: setConversationsOpen,
      Analytics: setAnalyticsOpen,
      Tests: setTestsOpen,
      Integrations: setIntegrationsOpen,
      "LLM Settings": setLLMSettingsOpen,
    };

    for (const group of navGroups) {
      for (const item of group.items) {
        if (item.children && hasActiveChild(item, currentPath)) {
          setterMap[item.title]?.(true);
        }
      }
    }
  }, [currentPath]);

  // Close the mobile drawer after successful route navigation.
  useEffect(() => {
    if (isMobile) {
      setOpenMobile(false);
    }
  }, [currentPath, isMobile, setOpenMobile]);

  const inWorkflowEditor = currentPath.startsWith("/ai-agents/workflow/");

  // ⌘K / Ctrl+K toggles the centered command-search palette.
  useEffect(() => {
    if (inWorkflowEditor) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inWorkflowEditor]);

  const filterItems = useCallback(
    (items: MenuItem[]): MenuItem[] => {
      return items.reduce<MenuItem[]>((acc, item) => {
        if (
          item.permissionsRequired &&
          !hasAnyPermission(item.permissionsRequired)
        )
          return acc;
        if (item.feature_flag) {
          // Feature-flagged navigation items should only render when the exact flag exists and is visible.
          const featureItem = getFeatureItem(item.feature_flag);
          if (featureItem?.visible !== true) return acc;
        }
        if (item.children) {
          const filteredChildren = filterItems(item.children);
          if (filteredChildren.length === 0) return acc;
          acc.push({ ...item, children: filteredChildren });
        } else {
          acc.push(item);
        }
        return acc;
      }, []);
    },
    [getFeatureItem]
  );

  // Permission/feature-flag filtered nav (no text search) — the command
  // palette consumes these and does its own fuzzy filtering.
  const navigableGroups = useMemo(
    () =>
      navGroups
        .map((group) => ({ ...group, items: filterItems(group.items) }))
        .filter((group) => group.items.length > 0),
    [filterItems]
  );

  const navigableFooter = useMemo(
    () => filterItems(footerItems),
    [filterItems]
  );

  const filteredGroups = useMemo(
    () =>
      navigableGroups
        .map((group) => ({
          ...group,
          items: filterBySearch(group.items, query),
        }))
        .filter((group) => group.items.length > 0),
    [navigableGroups, query]
  );

  const filteredFooter = useMemo(
    () => filterBySearch(navigableFooter, query),
    [navigableFooter, query]
  );

  const hasResults = filteredGroups.length > 0 || filteredFooter.length > 0;
  const searching = query.trim().length > 0;

  const handleLogout = () => {
    STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
    logout();
    toast.success("Logged out successfully.");
    window.location.href = "/login";
  };

  return (
    <Sidebar variant="floating" side="left">
      <CommandSearchDialog
        open={commandOpen}
        onOpenChange={setCommandOpen}
        groups={navigableGroups}
        footer={navigableFooter}
      />
      <SidebarContent
        className="flex flex-col bg-white dark:bg-zinc-900"
        style={{ height: "100%" }}
      >
        {/* Logo */}
        <div className="flex items-center px-5 pb-3 pt-5">
          <GenAssistLogo width={150} className="text-zinc-900 dark:text-zinc-100" />
          <NotificationBellPopover
            compact
            className="ml-auto mr-2 shrink-0 !border-0 !bg-transparent shadow-none hover:!bg-transparent"
          />
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400 dark:text-zinc-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search menu…"
              aria-label="Search menu"
              className={cn(
                "w-full rounded-md border border-zinc-200 bg-zinc-50 py-1.5 pl-8 pr-10 text-sm text-zinc-700",
                "placeholder:text-zinc-400 transition-colors",
                "focus:border-zinc-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-zinc-100",
                "dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:placeholder:text-zinc-500",
                "dark:focus:border-zinc-600 dark:focus:bg-zinc-800 dark:focus:ring-zinc-700"
              )}
            />
            <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-zinc-200 bg-white px-1 py-0.5 text-[10px] font-medium text-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-500">
              ⌘K
            </kbd>
          </div>
        </div>

        {/* Scrollable nav */}
        <nav className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 pb-2">
          {filteredGroups.map((group, gIdx) => (
            <SidebarGroup key={group.label} className="p-0">
              <div
                className={cn(
                  "px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500",
                  gIdx === 0 ? "pt-1" : "pt-4"
                )}
              >
                {group.label}
              </div>
              <SidebarGroupContent>
                <SidebarMenu className="gap-0.5">
                  {group.items.map((item, iIdx) => (
                    <SidebarMenuItem key={iIdx}>
                      {item.children ? (
                        <CollapsibleMenuItem
                          item={item}
                          currentPath={currentPath}
                          isOpen={
                            searching || (openMap[item.title] ?? false)
                          }
                          onToggle={toggleMap[item.title]}
                        />
                      ) : (
                        <NavLink item={item} currentPath={currentPath} />
                      )}
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}

          {searching && !hasResults && (
            <p className="px-2.5 py-6 text-center text-sm text-zinc-400 dark:text-zinc-500">
              No menu items match “{query.trim()}”.
            </p>
          )}
        </nav>

        {/* Pinned footer nav */}
        {filteredFooter.length > 0 && (
          <div className="border-t border-zinc-100 dark:border-zinc-800 px-3 py-2">
            <SidebarMenu className="gap-0.5">
              {filteredFooter.map((item, iIdx) => (
                <SidebarMenuItem key={iIdx}>
                  <NavLink item={item} currentPath={currentPath} />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </div>
        )}

        {/* User profile */}
        {username && (
          <UserFooter
            username={username}
            tenantId={tenantId}
            onLogout={handleLogout}
          />
        )}
      </SidebarContent>
    </Sidebar>
  );
}
