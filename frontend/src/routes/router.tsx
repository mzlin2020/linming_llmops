import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/app-shell/AppShell";
import { Placeholder } from "@/components/shared/Placeholder";
import { AppsPage } from "@/features/apps/AppsPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { DatasetsListView } from "@/features/datasets/DatasetsListView";
import { DatasetDetailLayout } from "@/features/datasets/detail/DatasetDetailLayout";
import { DatasetSettingsView } from "@/features/datasets/detail/DatasetSettingsView";
import { DocumentsView } from "@/features/datasets/detail/DocumentsView";
import { HitTestingView } from "@/features/datasets/detail/HitTestingView";
import { SegmentsView } from "@/features/datasets/segments/SegmentsView";
import { HomePage } from "@/features/home/HomePage";
import { BuiltinToolsView } from "@/features/plugins/builtin/BuiltinToolsView";
import { CustomToolEditor } from "@/features/plugins/custom/CustomToolEditor";
import { CustomToolsView } from "@/features/plugins/custom/CustomToolsView";
import { PluginsLayout } from "@/features/plugins/PluginsLayout";
import { PluginStoreView } from "@/features/plugins/store/PluginStoreView";
import { SettingsLayout } from "@/features/settings/SettingsLayout";
import { WorkflowPage } from "@/features/workflow/WorkflowPage";
import { RequireAuth } from "./guards";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: "apps/*", element: <AppsPage /> },
      {
        path: "plugins",
        element: <PluginsLayout />,
        children: [
          { index: true, element: <Navigate to="builtin" replace /> },
          { path: "builtin", element: <BuiltinToolsView /> },
          { path: "custom", element: <CustomToolsView /> },
          { path: "custom/new", element: <CustomToolEditor /> },
          { path: "custom/:id", element: <CustomToolEditor /> },
          { path: "store", element: <PluginStoreView /> },
        ],
      },
      {
        path: "datasets",
        children: [
          { index: true, element: <DatasetsListView /> },
          {
            path: ":id",
            element: <DatasetDetailLayout />,
            children: [
              { index: true, element: <Navigate to="documents" replace /> },
              { path: "documents", element: <DocumentsView /> },
              { path: "hit-testing", element: <HitTestingView /> },
              { path: "settings", element: <DatasetSettingsView /> },
            ],
          },
          { path: ":id/documents/:docId/segments", element: <SegmentsView /> },
        ],
      },
      { path: "workflow", element: <WorkflowPage /> },
      {
        path: "settings",
        element: <SettingsLayout />,
        children: [
          { index: true, element: <Navigate to="api-keys" replace /> },
          { path: "api-keys", element: <Placeholder title="API 密钥" note="Phase 5f 实现" /> },
          { path: "models", element: <Placeholder title="模型目录" note="Phase 5f 实现" /> },
          { path: "account", element: <Placeholder title="账户" note="Phase 5f 实现" /> },
        ],
      },
      { path: "*", element: <Placeholder title="页面不存在" note="404" /> },
    ],
  },
]);
