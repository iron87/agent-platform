import { useState } from "react";
import { replayRun } from "../../lib/services/replay-service";
import type { ApiErrorView, ConsoleProfile, RunResult } from "../../lib/types";
import { OperationState } from "../shared/OperationState";
import { JsonViewer } from "../ui/json-viewer";

interface ReplayPanelProps {
  profile: ConsoleProfile | null;
  onOperation: (name: string, success: boolean, payload?: unknown, error?: ApiErrorView) => void;
}

export function ReplayPanel({ profile, onOperation }: ReplayPanelProps) {
  const [traceId, setTraceId] = useState("");
  const [overrideInput, setOverrideInput] = useState("");
  const [overrideAgentId, setOverrideAgentId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorView | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);

  const runReplay = async () => {
    if (!profile) {
      setError({ code: "PROFILE_REQUIRED", message: "Select a profile first" });
      return;
    }
    if (!traceId.trim() || !overrideAgentId.trim() || !overrideInput.trim()) {
      setError({ code: "VALIDATION", message: "traceId, overrideAgentId and overrideInput are required" });
      return;
    }

    setLoading(true);
    try {
      const payload = await replayRun(profile, {
        sourceRunId: traceId.trim(),
        overrideInput,
        overrideAgentId,
      });
      setResult(payload);
      setError(null);
      onOperation("replay", true, payload);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("replay", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="mb-3 panel-title">Replay</h2>
      <OperationState loading={loading} error={error} onRetry={runReplay}>
        <div className="grid gap-2 md:grid-cols-2">
          <input
            className="input-modern"
            placeholder="Trace ID"
            value={traceId}
            onChange={(event) => setTraceId(event.target.value)}
          />
          <input
            className="input-modern"
            placeholder="Override Agent ID"
            value={overrideAgentId}
            onChange={(event) => setOverrideAgentId(event.target.value)}
          />
          <textarea
            className="input-modern min-h-24 md:col-span-2"
            placeholder="Override Input"
            value={overrideInput}
            onChange={(event) => setOverrideInput(event.target.value)}
          />
          <button className="btn-primary md:col-span-2" type="button" onClick={runReplay}>
            Execute replay
          </button>
        </div>
        {result ? <JsonViewer data={result} /> : null}
      </OperationState>
    </section>
  );
}
