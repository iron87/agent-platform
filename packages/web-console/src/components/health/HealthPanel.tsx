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
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold">Health</h2>
        <button
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
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
        <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {latestError.message}
          {latestError.traceId ? <div className="mt-1 text-xs">Trace: {latestError.traceId}</div> : null}
        </div>
      ) : null}

      {latestPayload ? (
        <div className="space-y-2">
          <div className="text-sm text-slate-700">Latest response</div>
          <JsonViewer data={latestPayload} />
        </div>
      ) : (
        <div className="text-sm text-slate-500">Run a health check to inspect dependencies.</div>
      )}
    </section>
  );
}
