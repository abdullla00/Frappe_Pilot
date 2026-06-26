export interface PilotAgent {
  name: string;
  agent_name: string;
  description?: string;
  provider?: string;
  model?: string;
  temperature?: number;
  disabled?: 0 | 1;
  instructions?: string;
  modified?: string;
}

export interface PilotAgentRun {
  name: string;
  agent?: string;
  status?: string;
  start_time?: string;
  end_time?: string;
  modified?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatResponse {
  reply: string;
  conversation_id?: string;
  run_id?: string;
}

export interface MeResponse {
  user: string;
  full_name: string;
  pilot_role: string | null;
  capabilities: string[];
}

export interface PilotRole {
  role_name: string;
  description?: string;
  capabilities?: string[];
}
