import { useState } from "react";
import { executeRun } from "../../lib/services/run-service";
import type { ApiErrorView, ConsoleProfile, RunResult } from "../../lib/types";
import { OperationState } from "../shared/OperationState";
import { JsonViewer } from "../ui/json-viewer";

interface RunPanelProps {
  profile: ConsoleProfile | null;
  onOperation: (name: string, success: boolean, payload?: unknown, error?: ApiErrorView) => void;
}

export function RunPanel({ profile, onOperation }: RunPanelProps) {
  const [agentId, setAgentId] = useState("");
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorView | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);

  const run = async () => {
    if (!profile) {
      setError({ code: "PROFILE_REQUIRED", message: "Select a profile first" });
      return;
    }
    if (!agentId.trim() || !input.trim()) {
      setError({ code: "VALIDATION", message: "agentId and input are required" });
      return;
    }

    setLoading(true);
    try {
      const payload = await executeRun(profile, {
        agentId: agentId.trim(),
        input,
        sessionId: sessionId.trim() || undefined,
      });
      setResult(payload);
      setError(null);
      onOperation("run", true, payload);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("run", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="mb-3 panel-title">Run</h2>
      <OperationState loading={loading} error={error} onRetry={run}>
        <div className="grid gap-2 md:grid-cols-2">
          <input
            className="input-modern"
            placeholder="Agent ID"
            value={agentId}
            onChange={(event) => setAgentId(event.target.value)}
          />
          <input
            className="input-modern"
            placeholder="Session ID (optional)"
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
          />
          <textarea
            className="input-modern min-h-32 md:col-span-2"
            placeholder="Input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button className="btn-primary md:col-span-2" type="button" onClick={run}>
            Execute run
          </button>
        </div>
        {result ? <JsonViewer data={result} /> : null}
      </OperationState>
    </section>
  );
}
