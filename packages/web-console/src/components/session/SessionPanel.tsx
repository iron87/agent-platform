import { useEffect, useMemo, useState } from "react";
import { listAgents } from "../../lib/services/agents-service";
import { sendSessionMessage } from "../../lib/services/session-service";
import { listConversationsByProfile, upsertConversation } from "../../lib/conversation-store";
import type { AgentSummary, ApiErrorView, ConsoleProfile, ConversationItem, SessionMessage } from "../../lib/types";
import { OperationState } from "../shared/OperationState";

interface SessionPanelProps {
  profile: ConsoleProfile | null;
  onOperation: (name: string, success: boolean, payload?: unknown, error?: ApiErrorView) => void;
}

export function SessionPanel({ profile, onOperation }: SessionPanelProps) {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorView | null>(null);

  useEffect(() => {
    if (!profile) {
      setAgents([]);
      setConversations([]);
      setSelectedAgentId("");
      setSelectedConversationId("");
      return;
    }

    const load = async () => {
      try {
        const all = await listAgents(profile);
        const chatCompatible = all.filter(
          (agent) => agent.graphType === "conversational" || agent.graphType === "tool_agent",
        );
        setAgents(chatCompatible);
        if (!selectedAgentId && chatCompatible.length > 0) {
          setSelectedAgentId(chatCompatible[0].agentId);
        }
      } catch (e) {
        const err = e as ApiErrorView;
        setError(err);
      }
    };

    load();
  }, [profile, selectedAgentId]);

  useEffect(() => {
    if (!profile) {
      return;
    }
    const stored = listConversationsByProfile(profile.id);
    setConversations(stored);
  }, [profile]);

  const activeConversation = useMemo(
    () => conversations.find((conv) => conv.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  );

  const conversationList = useMemo(
    () => conversations.filter((conv) => conv.agentId === selectedAgentId),
    [conversations, selectedAgentId],
  );

  const createConversation = () => {
    if (!profile || !selectedAgentId) {
      setError({ code: "VALIDATION", message: "Select a profile and agent first" });
      return;
    }

    const now = new Date().toISOString();
    const sessionId = crypto.randomUUID().slice(0, 8);
    const next: ConversationItem = {
      id: crypto.randomUUID(),
      profileId: profile.id,
      agentId: selectedAgentId,
      sessionId,
      title: `Conversation ${sessionId}`,
      updatedAt: now,
      messages: [],
    };

    upsertConversation(next);
    const updated = listConversationsByProfile(profile.id);
    setConversations(updated);
    setSelectedConversationId(next.id);
  };

  const send = async () => {
    if (!profile) {
      setError({ code: "PROFILE_REQUIRED", message: "Select a profile first" });
      return;
    }
    if (!selectedAgentId || !activeConversation || !content.trim()) {
      setError({ code: "VALIDATION", message: "Select an agent, a conversation, and type a message" });
      return;
    }

    const userMessage: SessionMessage = {
      sessionId: activeConversation.sessionId,
      role: "user",
      content,
      createdAt: new Date().toISOString(),
    };

    setLoading(true);
    try {
      const reply = await sendSessionMessage(profile, {
        agentId: selectedAgentId,
        sessionId: activeConversation.sessionId,
        content,
      });

      const updatedConversation: ConversationItem = {
        ...activeConversation,
        updatedAt: new Date().toISOString(),
        messages: [...activeConversation.messages, userMessage, reply],
      };
      upsertConversation(updatedConversation);
      const updated = listConversationsByProfile(profile.id);
      setConversations(updated);
      setContent("");
      setError(null);
      onOperation("session.send", true, reply);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("session.send", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="mb-3 panel-title">Agent Conversations</h2>
      <OperationState loading={loading} error={error} onRetry={send}>
        <div className="grid gap-4 xl:grid-cols-[220px_260px_1fr]">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">Agents</div>
            {agents.length === 0 ? (
              <div className="text-sm text-teal-800/70">No conversational/tool agents available.</div>
            ) : (
              <ul className="space-y-2">
                {agents.map((agent) => (
                  <li key={agent.agentId}>
                    <button
                      type="button"
                      className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                        selectedAgentId === agent.agentId
                          ? "border-teal-400 bg-teal-50 text-teal-900"
                          : "border-teal-100 bg-white text-teal-800 hover:bg-teal-50/60"
                      }`}
                      onClick={() => {
                        setSelectedAgentId(agent.agentId);
                        setSelectedConversationId("");
                      }}
                    >
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-xs text-teal-700/70">{agent.graphType ?? "unknown"}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">Conversations</div>
              <button
                type="button"
                className="btn-secondary px-2 py-1 text-xs"
                onClick={createConversation}
              >
                New
              </button>
            </div>
            {conversationList.length === 0 ? (
              <div className="text-sm text-teal-800/70">No conversations for selected agent.</div>
            ) : (
              <ul className="space-y-2">
                {conversationList.map((conversation) => (
                  <li key={conversation.id}>
                    <button
                      type="button"
                      className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                        selectedConversationId === conversation.id
                          ? "border-teal-400 bg-teal-50 text-teal-900"
                          : "border-teal-100 bg-white text-teal-800 hover:bg-teal-50/60"
                      }`}
                      onClick={() => setSelectedConversationId(conversation.id)}
                    >
                      <div className="font-medium">{conversation.title}</div>
                      <div className="text-xs text-teal-700/70">{conversation.sessionId}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">Chat</div>
            {activeConversation ? (
              <>
                <div className="max-h-96 space-y-2 overflow-auto rounded-xl border border-teal-100 bg-teal-50/50 p-3">
                  {activeConversation.messages.length === 0 ? (
                    <div className="text-sm text-teal-800/70">Start the conversation.</div>
                  ) : (
                    activeConversation.messages.map((message, index) => (
                      <article
                        key={`${message.createdAt ?? "msg"}-${index}`}
                        className="rounded-xl border border-teal-100 bg-white p-3"
                      >
                        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-teal-700">{message.role}</div>
                        <div className="text-sm text-teal-950">{message.content}</div>
                        {message.status ? (
                          <div className="mt-2 text-xs text-teal-700/70">Status: {message.status}</div>
                        ) : null}
                        {message.pendingApprovalId ? (
                          <div className="text-xs text-amber-700">Pending approval: {message.pendingApprovalId}</div>
                        ) : null}
                        {message.traceId ? (
                          <div className="text-xs text-teal-700/70">Trace: {message.traceId}</div>
                        ) : null}
                      </article>
                    ))
                  )}
                </div>
                <textarea
                  className="input-modern min-h-24"
                  placeholder="Type message"
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                />
                <button
                  className="btn-primary"
                  type="button"
                  onClick={send}
                >
                  Send
                </button>
              </>
            ) : (
              <div className="text-sm text-teal-800/70">Select or create a conversation to start chatting.</div>
            )}
          </div>
        </div>
      </OperationState>
    </section>
  );
}
