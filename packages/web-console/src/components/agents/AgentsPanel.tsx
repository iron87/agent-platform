import { useEffect, useState } from "react";
import { createAgent, listAgents } from "../../lib/services/agents-service";
import type { AgentSummary, ApiErrorView, ConsoleProfile } from "../../lib/types";
import { OperationState } from "../shared/OperationState";

const AVAILABLE_TOOLS = ["web_search", "code_exec", "rest_caller", "file_ops"] as const;

interface AgentsPanelProps {
  profile: ConsoleProfile | null;
  onOperation: (name: string, success: boolean, payload?: unknown, error?: ApiErrorView) => void;
}

export function AgentsPanel({ profile, onOperation }: AgentsPanelProps) {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [name, setName] = useState("");
  const [promptText, setPromptText] = useState("You are a helpful assistant.");
  const [graphType, setGraphType] = useState<"conversational" | "tool_agent" | "batch_agent">("conversational");
  const [enabledTools, setEnabledTools] = useState<string[]>([]);
  const [hitlTools, setHitlTools] = useState<string[]>([]);
  const [modelAlias, setModelAlias] = useState<"default" | "fast" | "embedding">("default");
  const [semanticMemoryEnabled, setSemanticMemoryEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorView | null>(null);

  const load = async () => {
    if (!profile) {
      const err = { code: "PROFILE_REQUIRED", message: "Select a profile first" };
      setError(err);
      setAgents([]);
      return;
    }

    setLoading(true);
    try {
      const data = await listAgents(profile);
      setAgents(data);
      setError(null);
      onOperation("agents.list", true, data);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("agents.list", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!profile) {
      setAgents([]);
      return;
    }
    load();
  }, [profile?.id]);

  const create = async () => {
    if (!profile) {
      const err = { code: "PROFILE_REQUIRED", message: "Select a profile first" };
      setError(err);
      return;
    }

    if (!name.trim() || !promptText.trim()) {
      setError({ code: "VALIDATION", message: "Agent name and prompt are required" });
      return;
    }

    if (graphType === "tool_agent" && enabledTools.length === 0) {
      setError({ code: "VALIDATION", message: "Select at least one tool for tool_agent" });
      return;
    }

    setLoading(true);
    try {
      const created = await createAgent(profile, {
        name: name.trim(),
        promptText: promptText.trim(),
        graphType,
        tools: graphType === "tool_agent" ? enabledTools : [],
        hitlTools: graphType === "tool_agent" ? hitlTools : [],
        modelAlias,
        semanticMemoryEnabled,
      });
      setAgents((prev) => {
        const existing = prev.filter((agent) => agent.agentId !== created.agentId);
        return [created, ...existing];
      });
      setName("");
      setPromptText("You are a helpful assistant.");
      setEnabledTools([]);
      setHitlTools([]);
      setError(null);
      onOperation("agents.create", true, created);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("agents.create", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="panel-title">Agents</h2>
          <p className="text-xs text-slate-500">All agents available for the selected tenant profile.</p>
        </div>
        <button className="btn-secondary" type="button" onClick={load}>
          Refresh
        </button>
      </div>

      <OperationState loading={loading} error={error} onRetry={load}>
        <div className="mb-3 grid gap-2 md:grid-cols-2">
          <input
            className="input-modern"
            placeholder="New agent name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-700">
            Graph
            <select
              className="input-modern"
              value={graphType}
              onChange={(event) => setGraphType(event.target.value as "conversational" | "tool_agent" | "batch_agent")}
            >
              <option value="conversational">conversational</option>
              <option value="tool_agent">tool_agent</option>
              <option value="batch_agent">batch_agent</option>
            </select>
          </label>
          <textarea
            className="input-modern min-h-28 md:col-span-2"
            placeholder="Agent prompt"
            value={promptText}
            onChange={(event) => setPromptText(event.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-700">
            Model
            <select
              className="input-modern"
              value={modelAlias}
              onChange={(event) => setModelAlias(event.target.value as "default" | "fast" | "embedding")}
            >
              <option value="default">default</option>
              <option value="fast">fast</option>
              <option value="embedding">embedding</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={semanticMemoryEnabled}
              onChange={(event) => setSemanticMemoryEnabled(event.target.checked)}
            />
            Semantic memory
          </label>

          {graphType === "tool_agent" ? (
            <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">Enabled tools</div>
              <div className="grid gap-2 md:grid-cols-2">
                {AVAILABLE_TOOLS.map((tool) => {
                  const selected = enabledTools.includes(tool);
                  return (
                    <label key={tool} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={(event) => {
                          setEnabledTools((prev) =>
                            event.target.checked ? [...prev, tool] : prev.filter((item) => item !== tool),
                          );
                          if (!event.target.checked) {
                            setHitlTools((prev) => prev.filter((item) => item !== tool));
                          }
                        }}
                      />
                      {tool}
                    </label>
                  );
                })}
              </div>

              <div className="mt-3 mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">HITL tools</div>
              <div className="grid gap-2 md:grid-cols-2">
                {enabledTools.length === 0 ? (
                  <div className="text-sm text-slate-500">Enable tools first.</div>
                ) : (
                  enabledTools.map((tool) => (
                    <label key={`hitl-${tool}`} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={hitlTools.includes(tool)}
                        onChange={(event) => {
                          setHitlTools((prev) =>
                            event.target.checked ? [...prev, tool] : prev.filter((item) => item !== tool),
                          );
                        }}
                      />
                      {tool}
                    </label>
                  ))
                )}
              </div>
            </div>
          ) : null}

          <button className="btn-primary md:col-span-2" type="button" onClick={create}>
            Create Agent
          </button>
        </div>

        {agents.length === 0 ? (
          <div className="text-sm text-teal-800/70">No agents loaded yet.</div>
        ) : (
          <>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {agents.length} agent{agents.length === 1 ? "" : "s"}
            </div>
            <ul className="space-y-2">
            {agents.map((agent) => (
              <li key={agent.agentId || agent.name} className="rounded-xl border border-teal-100 bg-white p-3 text-sm">
                <div className="font-medium text-teal-950">{agent.name}</div>
                <div className="mt-1 text-xs text-teal-800/65">{agent.agentId}</div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {agent.graphType ? (
                    <span className="rounded-full bg-teal-100 px-2 py-0.5 text-xs text-teal-800">{agent.graphType}</span>
                  ) : null}
                  {agent.modelAlias ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">{agent.modelAlias}</span>
                  ) : null}
                  {(agent.tools || []).map((tool) => (
                    <span key={`${agent.agentId}-${tool}`} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                      {tool}
                    </span>
                  ))}
                </div>
              </li>
            ))}
            </ul>
          </>
        )}
      </OperationState>
    </section>
  );
}
