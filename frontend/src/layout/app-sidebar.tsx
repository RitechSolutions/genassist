import {
  Home,
  Settings,
  Lock,
  LogOut,
  Users,
  ScrollText,
  ChevronRight,
  Settings2,
  LineChart,
  MessageSquare,
  UserRoundCog,
  Network,
  Waypoints,
  ListChecks,
  ChevronsUpDown,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/sidebar";
import { useLocation } from "react-router";
import { Link } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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

// ---------------------------------------------------------------------------
// Types & data
// ---------------------------------------------------------------------------

type MenuItem = {
  title: string;
  icon?: React.ElementType;
  url: string;
  permissionsRequired?: string[];
  children?: MenuItem[];
  feature_flag?: string;
  badge?: string;
};

const menuItems: MenuItem[] = [
  { title: "Dashboard", icon: Home, url: "/dashboard" },
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
    ],
  },
  {
    title: "Conversations",
    icon: MessageSquare,
    url: "/transcripts",
    permissionsRequired: ["read:conversation"],
  },
  {
    title: "Operators",
    icon: Users,
    url: "/operators",
    permissionsRequired: ["read:operator"],
  },
  {
    title: "Agent Studio",
    icon: UserRoundCog,
    url: "/ai-agents",
    permissionsRequired: ["read:llm_analyst"],
  },
  {
    title: "Tests",
    icon: ListChecks,
    url: "#",
    permissionsRequired: ["test:workflow"],
    badge: "BETA",
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
    ],
  },
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
        feature_flag: FeatureFlags.ADMIN_TOOLS.APP_SETTINGS,
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
        title: "LLM Analyst",
        url: "/llm-analyst",
        permissionsRequired: ["read:llm_analyst"],
      },
      {
        title: "Fine-Tune",
        url: "/fine-tune",
        permissionsRequired: ["*", "update:llm_provider"],
      },
      {
        title: "Local Fine-Tune",
        url: "/local-fine-tune",
        permissionsRequired: ["*", "update:llm_provider"],
        feature_flag: FeatureFlags.LLM_SETTINGS.SHOW_LOCAL_FINE_TUNE,
      },
    ],
  },
  {
    title: "Admin",
    icon: Settings2,
    url: "#",
    children: [
      {
        title: "Users",
        url: "/users",
        permissionsRequired: ["read:user"],
      },
      {
        title: "Roles",
        url: "/roles",
        permissionsRequired: ["read:role"],
      },
      {
        title: "User Types",
        url: "/user-types",
        permissionsRequired: ["read:user_type"],
      },
      {
        title: "User Groups",
        url: "/user-groups",
        permissionsRequired: ["read:user_group"],
      },
    ],
  },
  {
    title: "Audit Log",
    icon: ScrollText,
    url: "/audit-logs",
    permissionsRequired: ["read:audit_log"],
  },
  {
    title: "Settings",
    icon: Settings,
    url: "/settings",
  },
];

const STORAGE_KEYS = [
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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

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
          ? "bg-zinc-100 text-zinc-900"
          : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-800"
      )}
    >
      {item.icon && (
        <item.icon
          className={cn(
            "h-4 w-4 shrink-0",
            active ? "text-zinc-700" : "text-zinc-500 group-hover/link:text-zinc-600"
          )}
          strokeWidth={2.25}
        />
      )}
      <span>{item.title}</span>
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
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-200",
          childActive
            ? "text-zinc-900"
            : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-800"
        )}
      >
        {item.icon && (
          <item.icon
            className={cn(
              "h-4 w-4 shrink-0",
              childActive
                ? "text-zinc-700"
                : "text-zinc-500 group-hover/parent:text-zinc-600"
            )}
            strokeWidth={2.25}
          />
        )}
        <span>{item.title}</span>
        {item.badge && (
          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-blue-600">
            {item.badge}
          </span>
        )}
        <ChevronRight
          strokeWidth={2.25}
          className={cn(
            "ml-auto h-3.5 w-3.5 shrink-0 text-zinc-400 transition-transform duration-200",
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
            <div className="absolute left-[18px] top-0 bottom-0 w-px bg-zinc-200" />
            {item.children?.map((child, i) => {
              const active = isPathActive(currentPath, child.url);
              return (
                <Link
                  key={i}
                  to={child.url}
                  className={cn(
                    "flex items-center rounded-md px-2.5 py-[6px] text-sm transition-colors duration-150",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-200",
                    active
                      ? "bg-zinc-100 font-semibold text-zinc-900"
                      : "font-medium text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
                  )}
                >
                  <span>{child.title}</span>
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
    <div className="border-t border-zinc-100 px-3 py-3">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className={cn(
              "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 transition-colors",
              "hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-200"
            )}
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-[11px] font-semibold text-zinc-600">
              {initials || "U"}
            </div>
            <div className="min-w-0">
              <div className="truncate text-[13px] font-medium text-zinc-600">
                {username}
              </div>
              {tenantId ? (
                <div className="truncate text-[11px] text-zinc-400">
                 Tenant: <span className="font-medium">{tenantId}</span>
                </div>
              ) : null}
            </div>
            <ChevronsUpDown className="ml-auto h-3.5 w-3.5 text-zinc-300" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-48">
          <DropdownMenuItem asChild className="flex items-center gap-2">
            <Link
              to="/change-password"
              className="flex items-center gap-2"
            >
              <Lock className="h-4 w-4" />
              <span>Change Password</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={onLogout}
            className="flex items-center gap-2 text-red-600"
          >
            <LogOut className="h-4 w-4" />
            <span>Logout</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AppSidebar() {
  const [username, setUsername] = useState<string>("");
  const [tenantId, setTenantId] = useState<string>("");
  const { getFeatureItem } = useFeatureFlag();

  const location = useLocation();
  const currentPath = location.pathname;

  // Persisted collapsible state
  const [isAnalyticsOpen, toggleAnalytics, setAnalyticsOpen] =
    usePersistedState("isAnalyticsOpen", false);
  const [isTestsOpen, toggleTests, setTestsOpen] =
    usePersistedState("isTestsOpen", false);
  const [isIntegrationsOpen, toggleIntegrations, setIntegrationsOpen] =
    usePersistedState("isIntegrationOpen", false);
  const [isLLMSettingsOpen, toggleLLMSettings, setLLMSettingsOpen] =
    usePersistedState("isLLMSettingsOpen", false);
  const [isAdminOpen, toggleAdmin, setAdminOpen] =
    usePersistedState("isAdminOpen", false);

  const toggleMap: Record<string, () => void> = useMemo(
    () => ({
      Analytics: toggleAnalytics,
      Tests: toggleTests,
      Integrations: toggleIntegrations,
      "LLM Settings": toggleLLMSettings,
      Admin: toggleAdmin,
    }),
    [toggleAnalytics, toggleTests, toggleIntegrations, toggleLLMSettings, toggleAdmin]
  );

  const openMap: Record<string, boolean> = useMemo(
    () => ({
      Analytics: isAnalyticsOpen,
      Tests: isTestsOpen,
      Integrations: isIntegrationsOpen,
      "LLM Settings": isLLMSettingsOpen,
      Admin: isAdminOpen,
    }),
    [isAnalyticsOpen, isTestsOpen, isIntegrationsOpen, isLLMSettingsOpen, isAdminOpen]
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
      Analytics: setAnalyticsOpen,
      Tests: setTestsOpen,
      Integrations: setIntegrationsOpen,
      "LLM Settings": setLLMSettingsOpen,
      Admin: setAdminOpen,
    };

    for (const item of menuItems) {
      if (item.children && hasActiveChild(item, currentPath)) {
        setterMap[item.title]?.(true);
      }
    }
  }, [currentPath]);

  const filterItems = useCallback(
    (items: MenuItem[]): MenuItem[] => {
      return items.reduce<MenuItem[]>((acc, item) => {
        if (item.permissionsRequired && !hasAnyPermission(item.permissionsRequired))
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

  const filteredMenuItems = filterItems(menuItems);

  const handleLogout = () => {
    STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
    logout();
    toast.success("Logged out successfully.");
    window.location.href = "/login";
  };

  return (
    <Sidebar variant="floating" side="left">
      <SidebarContent
        className="bg-white flex flex-col"
        style={{ height: "100%" }}
      >
        {/* Logo */}
        <div className="flex items-center px-5 pt-5 pb-4">
          <GenAssistLogo width={150} />
        </div>

        {/* Scrollable nav */}
        <nav className="flex-1 overflow-y-auto px-3 pb-2">
          <SidebarGroup className="p-0">
            <SidebarGroupContent>
              <SidebarMenu className="gap-0.5">
                {filteredMenuItems.map((item, iIdx) => (
                  <SidebarMenuItem key={iIdx}>
                    {item.children ? (
                      <CollapsibleMenuItem
                        item={item}
                        currentPath={currentPath}
                        isOpen={openMap[item.title] ?? false}
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
        </nav>

        {/* Pinned footer */}
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
