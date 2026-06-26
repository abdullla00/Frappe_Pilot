import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { PermissionsProvider } from '@/contexts/PermissionsContext';
import { AppLayout } from '@/components/AppLayout';
import { HomePage } from '@/pages/HomePage';
import { AgentsPage } from '@/pages/AgentsPage';
import { AgentFormPage } from '@/pages/AgentFormPage';
import { ChatPage } from '@/pages/ChatPage';
import { ExecutionsPage } from '@/pages/ExecutionsPage';
import { KnowledgePage } from '@/pages/KnowledgePage';
import { FlowsPage } from '@/pages/FlowsPage';
import { McpPage } from '@/pages/McpPage';
import { RolesPage } from '@/pages/RolesPage';
import { SettingsRedirect } from '@/pages/SettingsRedirect';

export default function App() {
  return (
    <PermissionsProvider>
      <BrowserRouter basename="/pilot">
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="agents/new" element={<AgentFormPage />} />
            <Route path="agents/:name" element={<AgentFormPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="executions" element={<ExecutionsPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="flows" element={<FlowsPage />} />
            <Route path="mcp" element={<McpPage />} />
            <Route path="roles" element={<RolesPage />} />
            <Route path="settings" element={<SettingsRedirect />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PermissionsProvider>
  );
}
