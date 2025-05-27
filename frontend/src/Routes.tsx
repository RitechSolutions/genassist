import { createBrowserRouter, Navigate } from "react-router-dom";
import { Outlet, RouterProvider } from "react-router-dom";
import ProtectedRoute from "@/layout/ProtectedRoute";
import { Register } from "@/views/Register";
import { ChangePassword, Login } from "@/views/Login";
import Index from "@/views/Index";
import Transcripts from "./views/Transcripts";
import Agents from "./views/Agents";
import Analytics from "@/views/Analytics";
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
import Tools from "@/views/Tools/Index";
import CreateTool from "@/views/Tools/pages/CreateTool";
import KnowledgeBase from "@/views/KnowledgeBase/Index";
import LangGraphView from "./views/LangGraph/Index";

import { FeatureFlags } from "./views/Settings/pages/FeatureFlags";
import { useFeatureFlag } from "./context/FeatureFlagContext";

const ProtectedLayout = () => (
  <ProtectedRoute>
    <Outlet />
  </ProtectedRoute>
);

export const RoutesProvider = () => {
  const { isEnabled } = useFeatureFlag();

  const routes = createBrowserRouter([
    {
      path: "/",
      element: <ProtectedLayout />,
      children: [
        { path: "", element: <Navigate to="/dashboard" replace /> },
        {
          path: "dashboard",
          element: <Index />,
        },
        {
          path: "transcripts",
          element: (
            <ProtectedRoute
              requiredPermissions={["read:conversation"]}
            >
              <Transcripts />
            </ProtectedRoute>
          ),
        },
        {
          path: "operators",
          element: (
            <ProtectedRoute requiredPermissions={["read:operator"]}>
              <Agents />
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
            <ProtectedRoute requiredPermissions={["*"]}>
              <Tools />
            </ProtectedRoute>
          ),
        },
        {
          path: "tools/create",
          element: (
            <ProtectedRoute requiredPermissions={["*"]}>
              <CreateTool />
            </ProtectedRoute>
          ),
        },
        {
          path: "tools/edit/:id",
          element: (
            <ProtectedRoute requiredPermissions={["*"]}>
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
            <ProtectedRoute requiredPermissions={["*"]}>
              <KnowledgeBase />
            </ProtectedRoute>
          ),
        },
        {
          path: "lang-graph",
          element: (
            <ProtectedRoute requiredPermissions={["*"]}>
              <LangGraphView />
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
        { path: "change-password", element: <ChangePassword /> },
      ],
    },
    { path: "login", element: <Login /> },
    { path: "register", element: <Register /> },
    { path: "*", element: <NotFound /> },
    { path: "unauthorized", element: <Unauthorized /> },
  ]);

  return <RouterProvider router={routes} />;
};
