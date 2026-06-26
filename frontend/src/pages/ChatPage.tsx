import { FormEvent, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getAgents, sendChatMessage } from '@/services/agentApi';
import type { ChatMessage, PilotAgent } from '@/types/pilot.types';

export function ChatPage() {
  const [searchParams] = useSearchParams();
  const initialAgent = searchParams.get('agent') || '';

  const [agents, setAgents] = useState<PilotAgent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState(initialAgent);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getAgents()
      .then((list) => {
        setAgents(list);
        if (!selectedAgent && list.length > 0) {
          setSelectedAgent(list[0].name);
        }
      })
      .catch((err: Error) => setError(err.message || 'Failed to load agents'));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedAgent || !input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);
    setError('');

    try {
      const response = await sendChatMessage(selectedAgent, userMessage, conversationId);
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: response.reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-3xl">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-slate-900">Chat</h2>
        <select
          value={selectedAgent}
          onChange={(e) => {
            setSelectedAgent(e.target.value);
            setMessages([]);
            setConversationId(undefined);
          }}
          className="mt-2 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-pilot-500 focus:outline-none focus:ring-1 focus:ring-pilot-500"
        >
          <option value="">Select agent…</option>
          {agents.map((agent) => (
            <option key={agent.name} value={agent.name}>
              {agent.agent_name || agent.name}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400 text-center py-8">
            Send a message to start the conversation.
          </p>
        )}
        {messages.map((msg, index) => (
          <div
            key={`${msg.role}-${index}`}
            className={[
              'max-w-[85%] rounded-lg px-3 py-2 text-sm',
              msg.role === 'user'
                ? 'ml-auto bg-pilot-600 text-white'
                : 'bg-slate-100 text-slate-800',
            ].join(' ')}
          >
            {msg.content}
          </div>
        ))}
        {loading && (
          <div className="text-sm text-slate-400">Agent is thinking…</div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={!selectedAgent || loading}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-pilot-500 focus:outline-none focus:ring-1 focus:ring-pilot-500 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={!selectedAgent || !input.trim() || loading}
          className="rounded-md bg-pilot-600 px-4 py-2 text-sm font-medium text-white hover:bg-pilot-700 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
