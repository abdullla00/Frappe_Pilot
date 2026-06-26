import { call } from '@/lib/frappe-sdk';
import type {
  ChatMessage,
  ChatResponse,
  MeResponse,
  PilotAgent,
  PilotAgentRun,
  PilotRole,
} from '@/types/pilot.types';

const API = 'frappe_pilot.ai.agent_api';

function unwrap<T>(result: { message?: T }): T {
  return result.message as T;
}

export async function getMe(): Promise<MeResponse> {
  const result = await call.get(`${API}.get_me`);
  return unwrap<MeResponse>(result);
}

export async function getAgents(): Promise<PilotAgent[]> {
  const result = await call.get(`${API}.get_agents`);
  return unwrap<PilotAgent[]>(result) ?? [];
}

export async function getAgent(name: string): Promise<PilotAgent> {
  const result = await call.get(`${API}.get_agent`, { name });
  return unwrap<PilotAgent>(result);
}

export async function createAgent(data: Partial<PilotAgent>): Promise<PilotAgent> {
  const result = await call.post(`${API}.create_agent`, { data });
  return unwrap<PilotAgent>(result);
}

export async function updateAgent(name: string, data: Partial<PilotAgent>): Promise<PilotAgent> {
  const result = await call.post(`${API}.update_agent`, { name, data });
  return unwrap<PilotAgent>(result);
}

export async function deleteAgent(name: string): Promise<void> {
  await call.post(`${API}.delete_agent`, { name });
}

export async function sendChatMessage(
  agentName: string,
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const result = await call.post(`${API}.send_message`, {
    agent_name: agentName,
    message,
    conversation_id: conversationId,
  });
  return unwrap<ChatResponse>(result);
}

export async function getConversationMessages(
  conversationId: string,
): Promise<ChatMessage[]> {
  const result = await call.get(`${API}.get_conversation_messages`, {
    conversation_id: conversationId,
  });
  return unwrap<ChatMessage[]>(result) ?? [];
}

export async function getExecutions(limit = 50): Promise<PilotAgentRun[]> {
  const result = await call.get(`${API}.get_executions`, { limit });
  return unwrap<PilotAgentRun[]>(result) ?? [];
}

export async function getRoles(): Promise<PilotRole[]> {
  const result = await call.get(`${API}.get_roles`);
  return unwrap<PilotRole[]>(result) ?? [];
}
