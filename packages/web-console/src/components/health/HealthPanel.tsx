import { useState } from "react";
import type { ApiErrorView, HealthResponse } from "../../lib/types";
import { JsonViewer } from "../ui/json-viewer";

interface HealthPanelProps {
  onRun: () => Promise<void>;
  latestPayload: HealthResponse | null;
  latestError: ApiErrorView | null;
}

export function HealthPanel({ onRun, latestPayload, latestError }: HealthPanelProps) {
  const [loading, setLoading] = useState(false);

  return (
    <section className="panel">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="panel-title">Health</h2>
        <button
          className="btn-primary"
          type="button"
          disabled={loading}
          onClick={async () => {
            setLoading(true);
            try {
              await onRun();
            } finally {
              setLoading(false);
            }
          }}
        >
          {loading ? "Checking..." : "Run health check"}
        </button>
      </div>

      {latestError ? (
        <div className="mb-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {latestError.message}
          {latestError.traceId ? <div className="mt-1 text-xs">Trace: {latestError.traceId}</div> : null}
        </div>
      ) : null}

      {latestPayload ? (
        <div className="space-y-2">
          <div className="text-sm text-teal-800">Latest response</div>
          <JsonViewer data={latestPayload} />
        </div>
      ) : (
        <div className="text-sm text-teal-800/70">Run a health check to inspect dependencies.</div>
      )}
    </section>
  );
}
