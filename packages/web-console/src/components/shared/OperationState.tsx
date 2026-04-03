import type { ReactNode } from "react";
import type { ApiErrorView } from "../../lib/types";

interface OperationStateProps {
  loading: boolean;
  error: ApiErrorView | null;
  onRetry?: () => void;
  children: ReactNode;
}

export function OperationState({ loading, error, onRetry, children }: OperationStateProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-teal-100 bg-teal-50 p-3 text-sm text-teal-800">
        Processing request...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          <div>{error.message}</div>
          <div className="mt-1 text-xs text-rose-700">{error.code}</div>
          {onRetry ? (
            <button
              type="button"
              className="mt-2 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700"
              onClick={onRetry}
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
