import {
  Home,
  MessageSquare,
  BarChart2,
  Settings,
  User,
  Bell,
  Lock,
  LogOut,
  Users,
  AudioLines,
  UserCog,
  Key,
  Code,
  UserCheck,
  ScrollText,
  ChevronDown,
  ChevronUp,
  FullscreenIcon,
  Brain,
  Settings2,
  LucideMessageCirclePlus,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/sidebar";
import { useLocation } from "react-router";
import { Link, useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { logout, getPermissions, hasAnyPermission } from "@/services/auth";
import toast from "react-hot-toast";
import { useEffect, useState } from "react";
import { UploadMediaDialog } from "@/views/MediaUpload";
import LangGraphView from "@/views/LangGraph/Index";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import { FeatureFlag } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";

type MenuItem = {
  title: string;
  icon?: React.ElementType;
  url: string;
  permissionsRequired?: string[];
  children?: MenuItem[];
  feature_flag?: string;
};

const notifications = [
  {
    id: "1",
    title: "New Transcript Available",
    description: "A new customer conversation transcript has been processed.",
    time: "2 hours ago",
    unread: true,
  },
  {
    id: "2",
    title: "Performance Update",
    description: "Your weekly performance metrics are now available.",
    time: "5 hours ago",
    unread: true,
  },
  {
    id: "3",
    title: "System Update",
    description: "The system will undergo maintenance in 24 hours.",
    time: "1 day ago",
    unread: false,
  },
];
const mainMenuItems: MenuItem[] = [
  {
    title: "Dashboard",
    icon: Home,
    url: "/dashboard",
  },
  {
    title: "Conversations",
    icon: LucideMessageCirclePlus,
    url: "#",
    children: [
      {
        title: "Transcripts",
        url: "/transcripts",
        permissionsRequired: ["read:conversation"],
      },
      {
        title: "Analytics",
        url: "/analytics",
        permissionsRequired: ["read:metrics"],
      },
    ],
  },
  {
    title: "Admin Tools",
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
        title: "LLM Analyst",
        url: "/llm-analyst",
        permissionsRequired: ["read:llm_analyst"],
      },
      {
        title: "LLM Providers",
        url: "/llm-providers",
        permissionsRequired: ["read:llm_provider"],
      },
      {
        title: "API Keys",
        url: "/api-keys",
        permissionsRequired: ["read:api_key"],
      },
      {
        title: "Data Sources",
        url: "/data-sources",
        permissionsRequired: ["read:data_source"],
      },
      {
        title: "App Settings",
        url: "/app-settings",
        permissionsRequired: ["read:app_setting"],
        feature_flag: FeatureFlags.ADMIN_TOOLS.APP_SETTINGS,
      },
    ],
  },
  {
    title: "GenAgent",
    icon: UserCog,
    url: "#",
    children: [
      {
        title: "Agents",
        url: "/ai-agents",
        permissionsRequired: ["read:llm_analyst"],
      },
      {
        title: "Tools",
        url: "/tools",
        permissionsRequired: ["*"],
      },
      {
        title: "Knowledge Base",
        url: "/knowledge-base",
        permissionsRequired: ["*"],
      },
      {
        title: "Graph Config",
        url: "/lang-graph",
        permissionsRequired: ["*"],
      },
    ],
  },
  {
    title: "Operators",
    icon: Users,
    url: "/operators",
    permissionsRequired: ["read:operator"],
  },
];

const settingsMenuItems: MenuItem[] = [
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

const getInitialAdminToolsState = () => {
  const savedState = localStorage.getItem("isAdminToolsOpen");
  return savedState ? JSON.parse(savedState) : false;
};

const getInitialConversationsState = () => {
  const savedState = localStorage.getItem("isConversationsOpen");
  return savedState ? JSON.parse(savedState) : false;
};

const getInitialGenAgentState = () => {
  const saved = localStorage.getItem("isGenAgentOpen");
  return saved ? JSON.parse(saved) : false;
};

export function AppSidebar() {
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isUploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [isAdminToolsOpen, setIsAdminToolsOpen] = useState(
    getInitialAdminToolsState
  );
  const [isConversationsOpen, setIsConversationsOpen] = useState(
    getInitialConversationsState
  );
  const [isGenAgentOpen, setIsGenAgentOpen] = useState(getInitialGenAgentState);
  const { isEnabled } = useFeatureFlag();

  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;

  useEffect(() => {
    const userPermissions = getPermissions();
    setPermissions(userPermissions);
  }, []);

  useEffect(() => {
    const isOnConversationsPage = mainMenuItems
      .find((item) => item.title === "Conversations")
      ?.children?.some((child) => child.url === currentPath);

    if (isOnConversationsPage) {
      setIsConversationsOpen(true);
    }
  }, [currentPath]);

  const hasPermission = (permissionsRequired: string[] = []): boolean => {
    if (permissionsRequired.length === 0) return true;
    return hasAnyPermission(permissionsRequired);
  };

  const filterMenuItems = (items: MenuItem[]): MenuItem[] => {
    return items.filter((item) => {
      // Check permission
      if (
        item.permissionsRequired &&
        !hasPermission(item.permissionsRequired)
      ) {
        return false;
      }

      // Check feature flag
      if (item.feature_flag && !isEnabled(item.feature_flag)) {
        return false;
      }

      // Filter children recursively
      if (item.children) {
        item.children = filterMenuItems(item.children);
        return item.children.length > 0;
      }

      return true;
    });
  };

  const filteredMainMenuItems = filterMenuItems(mainMenuItems);
  const filteredSettingsMenuItems = filterMenuItems(settingsMenuItems);

  const handleToggleAdminTools = () => {
    setIsAdminToolsOpen((prev) => {
      const newAdminState = !prev;
      localStorage.setItem("isAdminToolsOpen", JSON.stringify(newAdminState));
      return newAdminState;
    });
  };

  const handleToggleConversations = () => {
    setIsConversationsOpen((prev) => {
      const newConversationsState = !prev;
      localStorage.setItem(
        "isConversationsOpen",
        JSON.stringify(newConversationsState)
      );
      return newConversationsState;
    });
  };

  const handleToggleGenAgent = () => {
    setIsGenAgentOpen((prev) => {
      const next = !prev;
      localStorage.setItem("isGenAgentOpen", JSON.stringify(next));
      return next;
    });
  };

  const handleLogout = () => {
    localStorage.removeItem("isAdminToolsOpen");
    logout();
    toast.success("Successfully logged out");
    window.location.href = "/login";
  };

  const linkClasses = `flex w-full h-full items-center gap-2 font-medium transition-colors duration-200 text-zinc-600 hover:text-primary hover:bg-zinc-100 px-3 rounded-md`;
  const parentMenuClasses = `flex w-full h-full items-center gap-2 font-medium transition-colors duration-200 text-zinc-700 hover:text-primary hover:bg-zinc-100 px-3 rounded-md`;
  const submenuLinkClasses = `flex h-full items-center gap-2 font-medium transition-colors duration-200 text-zinc-600 hover:text-primary hover:bg-zinc-100 py-2 px-3 text-sm rounded-md w-[calc(100%-24px)] ml-2`;
  const activeSubmenuClasses = `bg-[#F5F5F5] text-zinc-900 font-medium`;
  const menuItemClasses = "h-9";

  return (
    <Sidebar>
      <SidebarContent className="bg-white">
        <div className="flex flex-row items-center justify-between p-4 mb-0">
          <svg
            width="175"
            viewBox="0 0 449 80"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M80 39.9985H63.301H40.0015V63.3039L16.699 40.0015L40.0015 16.6961L59.1801 35.8776H75.8791L40.0015 0L0 40.0015L40.0015 80L80.0029 40.0015L80 39.9985Z"
              fill="#2100B1"
            />
            <path
              d="M131.01 33.5899H124.958C124.164 30.3133 122.762 28.0255 120.743 26.7296C118.727 25.4337 115.825 24.7843 112.044 24.7843C108.262 24.7843 105.659 25.3688 103.805 26.5407C101.948 27.7126 100.507 29.4218 99.4831 31.6741C98.4558 33.9264 97.9422 36.53 97.9422 39.4819C97.9422 42.4338 98.4558 45.0758 99.4831 47.2897C100.51 49.5037 101.969 51.1892 103.861 52.3405C105.753 53.4947 108.244 54.0703 111.344 54.0703C113.974 54.0703 116.017 53.7722 117.475 53.1788C118.933 52.5855 120.167 51.3427 121.177 49.4506C122.186 47.5584 122.995 44.9754 123.609 41.6959H112.371V37.265H126.906C127.987 37.265 128.79 37.5543 129.312 38.1299C129.835 38.7056 130.204 39.5882 130.419 40.7778L133.876 57.7986H129.12L126.419 46.1828C125.554 49.2823 124.527 51.7294 123.341 53.5301C122.006 55.5846 120.468 56.9809 118.721 57.7189C116.973 58.4569 114.461 58.8259 111.185 58.8259C106.609 58.8259 103.008 58.0436 100.378 56.4761C97.7474 54.9087 95.6958 52.6859 94.2169 49.8048C92.7409 46.9237 92.0029 43.4818 92.0029 39.4849C92.0029 35.488 92.7498 32.0283 94.2464 29.1118C95.7401 26.1953 97.8743 23.9519 100.649 22.3844C103.421 20.8169 107.258 20.0347 112.159 20.0347C116.229 20.0347 119.462 20.5394 121.859 21.546C124.253 22.5556 126.263 24.0581 127.884 26.0566C129.504 28.055 130.549 30.5671 131.018 33.5928L131.01 33.5899Z"
              fill="#231F20"
            />
            <path
              d="M139.275 57.7956V21.056H171.855V25.6492H145.111V36.8872H170.828V41.3711H145.111V53.1493H171.855V57.7956H139.275Z"
              fill="#231F20"
            />
            <path
              d="M177.257 57.7956V21.056H183.524L208.542 50.8822V21.056H214.322V57.7956H208.055L183.093 27.9694V57.7956H177.257Z"
              fill="#231F20"
            />
            <path
              d="M254.577 57.7956L252.038 51.5287H233.669L231.13 57.7956H219.189L234.427 21.056H251.339L266.521 57.7956H254.58H254.577ZM237.341 42.6139H248.416L243.336 30.1332H242.418L237.338 42.6139H237.341Z"
              fill="#231F20"
            />
            <path
              d="M278.945 32.0755C278.945 33.0467 279.603 33.6164 280.917 33.7788C282.23 33.9411 283.574 34.1035 284.943 34.2659C286.313 34.4282 287.833 34.6083 289.51 34.8061C291.184 35.0038 292.742 35.2105 294.183 35.4289C295.623 35.6444 297.09 35.9248 298.587 36.2673C300.081 36.6097 301.371 37.1853 302.451 37.9971C303.531 38.8089 304.323 39.9247 304.827 41.3475C305.332 42.7703 305.583 44.4175 305.583 46.292C305.583 49.7133 304.854 52.3346 303.396 54.1529C301.937 55.9713 299.918 57.1787 297.344 57.772C294.767 58.3653 291.553 58.6635 287.7 58.6635C283.848 58.6635 280.406 58.3653 277.705 57.772C275.004 57.1787 272.708 56.0156 270.815 54.2887C268.923 52.5619 267.979 49.5332 267.979 45.2116H277.867C277.867 46.6875 278.685 47.8506 280.326 48.6948C281.965 49.542 284.314 49.9642 287.379 49.9642C290.655 49.9642 292.837 49.604 293.917 48.8838C294.997 48.1635 295.538 47.3547 295.538 46.4514C295.538 45.6957 294.989 45.1732 293.89 44.8839C292.792 44.5946 291.405 44.2994 289.731 43.9924C288.057 43.6854 286.399 43.4434 284.76 43.2633C283.122 43.0832 281.554 42.912 280.061 42.7497C278.567 42.5873 277.062 42.2892 275.55 41.8582C274.039 41.4272 272.722 40.8398 271.606 40.1018C270.491 39.3638 269.608 38.2657 268.959 36.8045C268.309 35.3463 267.987 33.7345 267.987 31.9693C267.987 29.0173 268.637 26.6824 269.933 24.9732C271.229 23.264 273.31 22.0656 276.173 21.3807C279.036 20.6959 282.54 20.3535 286.682 20.3535C290.823 20.3535 294.283 20.6959 296.73 21.3807C299.18 22.0656 301.25 23.3172 302.944 25.1356C304.635 26.954 305.483 29.6284 305.483 33.1589H295.865C295.865 32.0431 295.071 31.125 293.489 30.4018C291.904 29.6815 289.725 29.3214 286.951 29.3214C283.565 29.3214 281.386 29.5634 280.412 30.0505C279.441 30.5376 278.954 31.2136 278.954 32.0755H278.945Z"
              fill="#231F20"
            />
            <path
              d="M321.356 32.0755C321.356 33.0467 322.014 33.6164 323.327 33.7788C324.641 33.9411 325.984 34.1035 327.354 34.2659C328.724 34.4282 330.244 34.6083 331.92 34.8061C333.594 35.0038 335.153 35.2105 336.593 35.4289C338.034 35.6444 339.501 35.9248 340.998 36.2673C342.491 36.6097 343.781 37.1853 344.862 37.9971C345.942 38.8089 346.733 39.9247 347.238 41.3475C347.743 42.7703 347.994 44.4175 347.994 46.292C347.994 49.7133 347.265 52.3346 345.806 54.1529C344.348 55.9713 342.329 57.1787 339.755 57.772C337.178 58.3653 333.963 58.6635 330.111 58.6635C326.259 58.6635 322.817 58.3653 320.116 57.772C317.415 57.1787 315.118 56.0156 313.226 54.2887C311.334 52.5619 310.389 49.5332 310.389 45.2116H320.278C320.278 46.6875 321.096 47.8506 322.737 48.6948C324.375 49.542 326.725 49.9642 329.789 49.9642C333.066 49.9642 335.247 49.604 336.328 48.8838C337.408 48.1635 337.948 47.3547 337.948 46.4514C337.948 45.6957 337.399 45.1732 336.301 44.8839C335.203 44.5946 333.816 44.2994 332.142 43.9924C330.468 43.6854 328.809 43.4434 327.171 43.2633C325.533 43.0832 323.965 42.912 322.471 42.7497C320.978 42.5873 319.472 42.2892 317.961 41.8582C316.449 41.4272 315.133 40.8398 314.017 40.1018C312.901 39.3638 312.019 38.2657 311.369 36.8045C310.72 35.3463 310.398 33.7345 310.398 31.9693C310.398 29.0173 311.047 26.6824 312.343 24.9732C313.639 23.264 315.72 22.0656 318.584 21.3807C321.447 20.6959 324.951 20.3535 329.093 20.3535C333.234 20.3535 336.694 20.6959 339.141 21.3807C341.591 22.0656 343.66 23.3172 345.355 25.1356C347.046 26.954 347.893 29.6284 347.893 33.1589H338.276C338.276 32.0431 337.482 31.125 335.9 30.4018C334.314 29.6815 332.136 29.3214 329.361 29.3214C325.975 29.3214 323.797 29.5634 322.823 30.0505C321.851 30.5376 321.364 31.2136 321.364 32.0755H321.356Z"
              fill="#231F20"
            />
            <path
              d="M352.315 57.7956V21.056H363.337V57.7956H352.315Z"
              fill="#231F20"
            />
            <path
              d="M378.629 32.0755C378.629 33.0467 379.287 33.6164 380.6 33.7788C381.914 33.9411 383.257 34.1035 384.627 34.2659C385.996 34.4282 387.517 34.6083 389.193 34.8061C390.867 35.0038 392.426 35.2105 393.866 35.4289C395.307 35.6444 396.774 35.9248 398.271 36.2673C399.764 36.6097 401.054 37.1853 402.135 37.9971C403.215 38.8089 404.006 39.9247 404.511 41.3475C405.016 42.7703 405.267 44.4175 405.267 46.292C405.267 49.7133 404.537 52.3346 403.079 54.1529C401.621 55.9713 399.602 57.1787 397.028 57.772C394.451 58.3653 391.236 58.6635 387.384 58.6635C383.532 58.6635 380.09 58.3653 377.389 57.772C374.688 57.1787 372.391 56.0156 370.499 54.2887C368.607 52.5619 367.662 49.5332 367.662 45.2116H377.551C377.551 46.6875 378.369 47.8506 380.01 48.6948C381.648 49.542 383.998 49.9642 387.062 49.9642C390.339 49.9642 392.52 49.604 393.601 48.8838C394.681 48.1635 395.221 47.3547 395.221 46.4514C395.221 45.6957 394.672 45.1732 393.574 44.8839C392.476 44.5946 391.089 44.2994 389.415 43.9924C387.741 43.6854 386.082 43.4434 384.444 43.2633C382.805 43.0832 381.238 42.912 379.744 42.7497C378.251 42.5873 376.745 42.2892 375.234 41.8582C373.722 41.4272 372.406 40.8398 371.29 40.1018C370.174 39.3638 369.292 38.2657 368.642 36.8045C367.993 35.3463 367.671 33.7345 367.671 31.9693C367.671 29.0173 368.32 26.6824 369.616 24.9732C370.912 23.264 372.993 22.0656 375.857 21.3807C378.72 20.6959 382.224 20.3535 386.365 20.3535C390.507 20.3535 393.967 20.6959 396.414 21.3807C398.864 22.0656 400.933 23.3172 402.628 25.1356C404.319 26.954 405.166 29.6284 405.166 33.1589H395.549C395.549 32.0431 394.755 31.125 393.173 30.4018C391.587 29.6815 389.409 29.3214 386.634 29.3214C383.248 29.3214 381.07 29.5634 380.096 30.0505C379.124 30.5376 378.637 31.2136 378.637 32.0755H378.629Z"
              fill="#231F20"
            />
            <path
              d="M422.069 57.7956V29.9708H407.968V21.056H447.193V29.9708H433.092V57.7956H422.069Z"
              fill="#231F20"
            />
          </svg>
          <FeatureFlag flagKey={FeatureFlags.UI.NOTIFICATIONS}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="relative p-2 hover:bg-gray-100 rounded-full transition-colors">
                  <Bell className="w-5 h-5 text-zinc-600" />
                  <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                {notifications.map((notification) => (
                  <DropdownMenuItem
                    key={notification.id}
                    className="flex flex-col items-start p-3 space-y-1"
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-medium">{notification.title}</span>
                      <span className="text-xs text-muted-foreground">
                        {notification.time}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {notification.description}
                    </p>
                    {notification.unread && (
                      <div className="flex items-center gap-1 text-xs text-primary">
                        <div className="w-1 h-1 rounded-full bg-primary" />
                        New
                      </div>
                    )}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuItem asChild className="p-3 border-t">
                  <Link
                    to="/notifications"
                    className="w-full text-primary hover:text-primary"
                  >
                    View all notifications
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </FeatureFlag>
        </div>
        <div className="p-2">
          <button
            onClick={() => setUploadDialogOpen(true)}
            className="w-full flex items-center justify-center gap-1 bg-black text-white font-semibold py-3 px-5 rounded-md hover:opacity-90 transition"
          >
            <AudioLines className="w-6 h-5" />
            Upload
          </button>

          <UploadMediaDialog
            isOpen={isUploadDialogOpen}
            onOpenChange={setUploadDialogOpen}
          />
        </div>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {filteredMainMenuItems.map((item, index) => (
                <SidebarMenuItem
                  key={index}
                  className={
                    ["Conversations", "Admin Tools", "GenAgent"].includes(
                      item.title
                    )
                      ? "h-fit"
                      : menuItemClasses
                  }
                >
                  {item.title === "Conversations" && item.children ? (
                    <div>
                      <div onClick={handleToggleConversations}>
                        <SidebarMenuButton className={parentMenuClasses}>
                          {item.icon && <item.icon className="w-4 h-4" />}
                          <span>{item.title}</span>
                          <div className="ml-auto transition-transform duration-200">
                            {isConversationsOpen ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </div>
                        </SidebarMenuButton>
                      </div>
                      {isConversationsOpen && (
                        <div className="relative ml-6 space-y-1 pt-1">
                          <div className="absolute top-0 bottom-0 w-[1.5px] bg-gray-200"></div>
                          <SidebarGroupContent>
                            {item.children.map((child, childIndex) => (
                              <SidebarMenuItem
                                key={childIndex}
                                className={`${menuItemClasses} relative`}
                              >
                                <SidebarMenuButton asChild className="pl-2">
                                  <Link
                                    to={child.url}
                                    className={`${submenuLinkClasses} ${
                                      child.url === currentPath
                                        ? activeSubmenuClasses
                                        : ""
                                    }`}
                                  >
                                    {child.icon && (
                                      <child.icon className="w-4 h-4 mr-2" />
                                    )}
                                    <span>{child.title}</span>
                                  </Link>
                                </SidebarMenuButton>
                              </SidebarMenuItem>
                            ))}
                          </SidebarGroupContent>
                        </div>
                      )}
                    </div>
                  ) : item.title === "GenAgent" && item.children ? (
                    <div>
                      <div onClick={handleToggleGenAgent}>
                        <SidebarMenuButton className={parentMenuClasses}>
                          {item.icon && <item.icon className="w-4 h-4" />}
                          <span>{item.title}</span>
                          <div className="ml-auto transition-transform duration-200">
                            {isGenAgentOpen ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </div>
                        </SidebarMenuButton>
                      </div>
                      {isGenAgentOpen && (
                        <div className="relative ml-6 space-y-1 pt-1">
                          <div className="absolute top-0 bottom-0 w-[1.5px] bg-gray-200"></div>
                          <SidebarGroupContent>
                            {item.children.map((child, i) => (
                              <SidebarMenuItem
                                key={i}
                                className={`${menuItemClasses} relative`}
                              >
                                <SidebarMenuButton asChild className="pl-2">
                                  <Link
                                    to={child.url}
                                    className={`${submenuLinkClasses} ${
                                      child.url === currentPath
                                        ? activeSubmenuClasses
                                        : ""
                                    }`}
                                  >
                                    {child.icon && (
                                      <child.icon className="w-4 h-4 mr-2" />
                                    )}
                                    <span>{child.title}</span>
                                  </Link>
                                </SidebarMenuButton>
                              </SidebarMenuItem>
                            ))}
                          </SidebarGroupContent>
                        </div>
                      )}
                    </div>
                  ) : item.children ? (
                    <div>
                      <div onClick={handleToggleAdminTools}>
                        <SidebarMenuButton className={parentMenuClasses}>
                          {item.icon && <item.icon className="w-4 h-4" />}
                          <span>{item.title}</span>
                          <div className="ml-auto transition-transform duration-200">
                            {isAdminToolsOpen ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </div>
                        </SidebarMenuButton>
                      </div>
                      {isAdminToolsOpen && (
                        <div className="relative ml-6 space-y-1 pt-1">
                          <div className="absolute top-0 bottom-0 w-[1.5px] bg-gray-200"></div>
                          <SidebarGroupContent>
                            {item.children.map((child, childIndex) => (
                              <SidebarMenuItem
                                key={childIndex}
                                className={`${menuItemClasses} relative`}
                              >
                                <SidebarMenuButton asChild className="pl-2">
                                  <Link
                                    to={child.url}
                                    className={`${submenuLinkClasses} ${
                                      child.url === currentPath
                                        ? activeSubmenuClasses
                                        : ""
                                    }`}
                                  >
                                    {child.icon && (
                                      <child.icon className="w-4 h-4 mr-2" />
                                    )}
                                    <span>{child.title}</span>
                                  </Link>
                                </SidebarMenuButton>
                              </SidebarMenuItem>
                            ))}
                          </SidebarGroupContent>
                        </div>
                      )}
                    </div>
                  ) : (
                    <Link
                      to={item.url}
                      className={`${linkClasses} ${
                        item.url === currentPath ? activeSubmenuClasses : ""
                      }`}
                    >
                      {item.icon && <item.icon className="w-4 h-4" />}
                      <span>{item.title}</span>
                    </Link>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <div className="mt-auto">
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {filteredSettingsMenuItems.map((item, index) => (
                  <SidebarMenuItem key={index} className={menuItemClasses}>
                    <SidebarMenuButton asChild className="h-full">
                      <Link
                        to={item.url}
                        className={`${linkClasses} ${
                          item.url === currentPath ? activeSubmenuClasses : ""
                        }`}
                      >
                        {item.icon && <item.icon className="w-5 h-5" />}
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}

                <SidebarMenuItem className={menuItemClasses}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className={linkClasses}>
                        <User className="w-5 h-5" />
                        <span>Account</span>
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem
                        asChild
                        className="flex items-center gap-2"
                      >
                        <Link
                          to="/change-password"
                          className="flex items-center gap-2"
                        >
                          <Lock className="w-4 h-4" />
                          <span>Change Password</span>
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={handleLogout}
                        className="flex items-center gap-2 text-red-600"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Logout</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </div>
      </SidebarContent>
    </Sidebar>
  );
}
