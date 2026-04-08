import { createBrowserRouter, Navigate } from "react-router-dom";
import { Outlet, RouterProvider } from "react-router-dom";
import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import ProtectedRoute from "@/layout/ProtectedRoute";
import { Register } from "@/views/Register";
import { ChangePassword, Login } from "@/views/Login";
import Index from "@/views/Index";
import Transcripts from "./views/Transcripts";
import Operators from "./views/Operators";
import Analytics from "@/views/Analytics";
import AgentPerformancePage from "@/views/Analytics/pages/AgentPerformancePage";
import NodeAnalyticsPage from "@/views/Analytics/pages/NodeAnalyticsPage";
import Notifications from "@/views/Notifications";
import Settings from "./views/Settings";
import NotFound from "@/views/NotFound";
import Roles from "@/views/Roles/pages/Roles";
import Users from "./views/Users/Index";
import UserTypes from "./views/UserTypes/pages/UserTypes";
import ApiKeys from "./views/ApiKeys/pages/ApiKeys";
import AppSettings from "./views/AppSettings/Index";
import AIAgents from "./views/AIAgents/Index";
import DataSources from "./views/DataSources/pages/DataSources";
import AuditLogs from "@/views/AuditLogs";
import Unauthorized from "@/views/Unauthorized";
import LlmAnalyst from "@/views/LlmAnalyst/Index";
import LLMProviders from "@/views/LlmProviders/Index";
import FineTune from "@/views/FineTune/Index";
import FineTuneJobDetail from "@/views/FineTune/pages/FineTuneJobDetail";
import Tools from "@/views/Tools/Index";
import CreateTool from "@/views/Tools/pages/CreateTool";
import KnowledgeBase from "@/views/KnowledgeBase/Index";
import KnowledgeBaseForm from "@/views/KnowledgeBase/pages/KnowledgeBaseForm";
import MLModels from "@/views/MLModels/Index";
import MLModelDetail from "@/views/MLModels/components/MLModelDetail";
import { FeatureFlags } from "./views/Settings/pages/FeatureFlags";
import { Translations } from "./views/Settings/pages/Translations";
import { Languages } from "./views/Settings/pages/Languages";
import { FileManagerFiles } from "./views/Settings/pages/FileManagerFiles";
import { useFeatureFlag } from "./context/FeatureFlagContext";
import { GlobalChat } from "./components/GlobalChat";
import ServerDownPage from "@/components/ServerDownPage";
import { useServerStatus } from "@/context/ServerStatusContext";
import { GmailOAuthCallback } from "./views/DataSources/components/GmailOAuthCallback";
import { Office365OAuthCallback  } from "./views/DataSources/components/Office365OAuthCallback";
import WebhookListPage from "@/views/Webhooks/pages/Webhooks";
import MCPServersPage from "@/views/MCPServers/pages/MCPServers";
import TestSuitesIndex from "@/views/TestSuites/Index";
import DatasetsPage from "@/views/TestSuites/pages/DatasetsPage";
import EvaluationsPage from "@/views/TestSuites/pages/EvaluationsPage";
import DatasetDetailPage from "@/views/TestSuites/pages/DatasetDetailPage";
import EvaluationDetailPage from "@/views/TestSuites/pages/EvaluationDetailPage";
import Privacy from "@/views/Privacy";
import ServerStatusBanner from "@/components/ServerStatusBanner";
import Onboarding from "@/views/Onboarding/pages/Onboarding";
import { getRegistrationStatus } from "@/services/registration";
import { RoutesContext } from "@/context/RoutesContext";
import { WebSocketDashboardProvider } from "@/context/WebSocketDashboardContext";

const getAccessToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";

const WebSocketDashboardLayout = ({ children }: { children: ReactNode }) => (
  <WebSocketDashboardProvider token={getAccessToken()}>
    {children}
  </WebSocketDashboardProvider>
);

const ProtectedLayout = () => {
  const { status, isOffline } = useServerStatus();
  const isDown = isOffline || status.down;

  return (
    <ProtectedRoute>
      {isDown ? (
        <ServerDownPage />
      ) : (
        <>
          <Outlet />
          <GlobalChat />
        </>
      )}
    </ProtectedRoute>
  );
};

export type RegistrationStatus = "loading" | "new" | "existing";

export const RoutesProvider = () => {
  const { isEnabled } = useFeatureFlag();

  const [registrationStatus, setRegistrationStatus] = useState<RegistrationStatus>("loading");
  const [skipOnboarding, setSkipOnboarding] = useState(false);

  const checkRegistration = useCallback(async () => {
    try {
      const response = await getRegistrationStatus();
      const isNew = Boolean(response?.is_new);
      setRegistrationStatus(isNew ? "new" : "existing");
    } catch (error) {
      setRegistrationStatus("existing");
    }
  }, [setRegistrationStatus]);

  useEffect(() => {
    // check if the user has skipped onboarding
    const skipFlag = localStorage.getItem("skip_onboarding") === "true";
    if (skipFlag) {
      setSkipOnboarding(true);
      setRegistrationStatus("existing");
      return;
    }

    // check the registration status
    checkRegistration();
  }, [checkRegistration]);

  // temporary skip handler
  useEffect(() => {
    const handleSkip = () => setRegistrationStatus("existing");
    window.addEventListener("skip-onboarding", handleSkip);
    return () => window.removeEventListener("skip-onboarding", handleSkip);
  }, []);

  const mainRouter = useMemo(
    () =>
      createBrowserRouter([
        {
          path: "/",
          element: <ProtectedLayout />,
          children: [
            { path: "", element: <Navigate to="/dashboard" replace /> },
            {
              path: "dashboard",
              element: (
                <WebSocketDashboardLayout>
                  <Index />
                </WebSocketDashboardLayout>
              ),
            },
            {
              path: "transcripts",
              element: (
                <ProtectedRoute
                  requiredPermissions={["read:conversation"]}
                >
                  <WebSocketDashboardLayout>
                    <Transcripts />
                  </WebSocketDashboardLayout>
                </ProtectedRoute>
              ),
            },
            {
              path: "operators",
              element: (
                <ProtectedRoute requiredPermissions={["read:operator"]}>
                  <Operators />
                </ProtectedRoute>
              ),
            },
            {
              path: "analytics",
              element: (
                <ProtectedRoute requiredPermissions={["read:llm_analyst"]}>
                  <Analytics />
                </ProtectedRoute>
              ),
            },
            {
              path: "analytics/agent-performance",
              element: (
                <ProtectedRoute requiredPermissions={["read:dashboard"]}>
                  <AgentPerformancePage />
                </ProtectedRoute>
              ),
            },
            {
              path: "analytics/node-analytics",
              element: (
                <ProtectedRoute requiredPermissions={["read:dashboard"]}>
                  <NodeAnalyticsPage />
                </ProtectedRoute>
              ),
            },
            {
              path: "notifications",
              element: <Notifications />,
            },
            {
              path: "settings",
              element: <Settings />,
            },
            {
              path: "settings/feature-flags",
              element: (
                <ProtectedRoute requiredPermissions={["read:feature_flag"]}>
                  <FeatureFlags />
                </ProtectedRoute>
              ),
            },
            {
              path: "settings/translations",
              element: (
                <ProtectedRoute requiredPermissions={["read:app_setting"]}>
                  <Translations />
                </ProtectedRoute>
              ),
            },
            {
              path: "settings/languages",
              element: (
                <ProtectedRoute requiredPermissions={["read:app_setting"]}>
                  <Languages />
                </ProtectedRoute>
              ),
            },
            {
              path: "settings/file-manager",
              element: (
                <ProtectedRoute requiredPermissions={["read:file"]}>
                  <FileManagerFiles />
                </ProtectedRoute>
              ),
            },
            {
              path: "users",
              element: (
                <ProtectedRoute requiredPermissions={["read:user"]}>
                  <Users />
                </ProtectedRoute>
              ),
            },
            {
              path: "roles",
              element: (
                <ProtectedRoute requiredPermissions={["read:role"]}>
                  <Roles />
                </ProtectedRoute>
              ),
            },
            {
              path: "llm-analyst",
              element: (
                <ProtectedRoute requiredPermissions={["read:llm_analyst"]}>
                  <LlmAnalyst />
                </ProtectedRoute>
              ),
            },
            {
              path: "llm-providers",
              element: (
                <ProtectedRoute requiredPermissions={["read:llm_provider"]}>
                  <LLMProviders />
                </ProtectedRoute>
              ),
            },
            {
              path: "fine-tune",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:llm_provider"]}>
                  <FineTune />
                </ProtectedRoute>
              ),
            },
            {
              path: "fine-tune/:id",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:llm_provider"]}>
                  <FineTuneJobDetail />
                </ProtectedRoute>
              ),
            },
            {
              path: "user-types",
              element: (
                <ProtectedRoute requiredPermissions={["read:user_type"]}>
                  <UserTypes />
                </ProtectedRoute>
              ),
            },
            {
              path: "api-keys",
              element: (
                <ProtectedRoute requiredPermissions={["read:api_key"]}>
                  <ApiKeys />
                </ProtectedRoute>
              ),
            },
            {
              path: "ai-agents",
              element: (
                <ProtectedRoute requiredPermissions={["read:llm_analyst"]}>
                  <AIAgents />
                </ProtectedRoute>
              ),
            },
            {
              path: "ai-agents/*",
              element: (
                <ProtectedRoute requiredPermissions={["read:llm_analyst"]}>
                  <AIAgents />
                </ProtectedRoute>
              ),
            },
            {
              path: "tools",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:app_settings"]}>
                  <Tools />
                </ProtectedRoute>
              ),
            },
            {
              path: "tools/create",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:app_settings"]}>
                  <CreateTool />
                </ProtectedRoute>
              ),
            },
            {
              path: "tools/edit/:id",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:app_settings"]}>
                  <CreateTool />
                </ProtectedRoute>
              ),
            },
            {
              path: "data-sources",
              element: (
                <ProtectedRoute requiredPermissions={["read:data_source"]}>
                  <DataSources />
                </ProtectedRoute>
              ),
            },
            {
              path: "audit-logs",
              element: (
                <ProtectedRoute requiredPermissions={["read:audit_log"]}>
                  <AuditLogs />
                </ProtectedRoute>
              ),
            },
            {
              path: "knowledge-base",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:knowledge_base"]}>
                  <KnowledgeBase />
                </ProtectedRoute>
              ),
            },
            {
              path: "knowledge-base/new",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:knowledge_base"]}>
                  <KnowledgeBaseForm />
                </ProtectedRoute>
              ),
            },
            {
              path: "knowledge-base/edit/:id",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:knowledge_base"]}>
                  <KnowledgeBaseForm />
                </ProtectedRoute>
              ),
            },
            {
              path: "ml-models",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:ml_model"]}>
                  <MLModels />
                </ProtectedRoute>
              ),
            },
            {
              path: "ml-models/:id",
              element: (
                <ProtectedRoute requiredPermissions={["*", "update:ml_model"]}>
                  <MLModelDetail />
                </ProtectedRoute>
              ),
            },
            {
              path: "tests",
              element: (
                <ProtectedRoute requiredPermissions={["test:workflow"]}>
                  <TestSuitesIndex />
                </ProtectedRoute>
              ),
            },
            {
              path: "tests/datasets",
              element: (
                <ProtectedRoute requiredPermissions={["test:workflow"]}>
                  <DatasetsPage />
                </ProtectedRoute>
              ),
            },
            {
              path: "tests/datasets/:datasetId",
              element: (
                <ProtectedRoute requiredPermissions={["test:workflow"]}>
                  <DatasetDetailPage />
                </ProtectedRoute>
              ),
            },
            {
              path: "tests/evaluations",
              element: (
                <ProtectedRoute requiredPermissions={["test:workflow"]}>
                  <EvaluationsPage />
                </ProtectedRoute>
              ),
            },
            {
              path: "tests/evaluations/:evaluationId",
              element: (
                <ProtectedRoute requiredPermissions={["test:workflow"]}>
                  <EvaluationDetailPage />
                </ProtectedRoute>
              ),
            },
            {
              path: "app-settings",
              element: (
                <ProtectedRoute requiredPermissions={["read:app_setting"]}>
                  <AppSettings />
                </ProtectedRoute>
              ),
            },
            {
              path: "webhooks",
              element: (
                <ProtectedRoute requiredPermissions={["read:webhook"]}>
                  <WebhookListPage />
                </ProtectedRoute>
              ),
            },
            {
              path: "mcp-servers",
              element: (
                <ProtectedRoute requiredPermissions={["read:mcp_server"]}>
                  <MCPServersPage />
                </ProtectedRoute>
              ),
            },

            { path: "change-password", element: <ChangePassword /> },
            {
              path: "gauth/callback",
              element: <GmailOAuthCallback />,
            },
          ],
        },
        { path: "login", element: (<><ServerStatusBanner /><Login /></>) },
        { path: "register", element: <Register /> },
        { path: "privacy", element: <Privacy /> },
        {
              path: "onboarding",
              element: <Onboarding />,
            },
        { path: "unauthorized", element: <Unauthorized /> },
        { path: "office365/oauth/callback", element: <Office365OAuthCallback />},
        { path: "*", element: <NotFound /> }
      ]),
    [isEnabled],
  );

  const organizationRouter = useMemo(
    () =>
      createBrowserRouter([
        { path: "onboarding", element: <Onboarding /> },
        { path: "*", element: <Navigate to="/onboarding" replace /> },
      ]),
    [],
  );

  if (registrationStatus === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center text-[#6b7280]">
        Loading...
      </div>
    );
  }

  const router = registrationStatus === "new" ? organizationRouter : mainRouter;

  return <RoutesContext.Provider value={{ registrationStatus, skipOnboarding }}>
    <RouterProvider router={router} />
  </RoutesContext.Provider>;
};
