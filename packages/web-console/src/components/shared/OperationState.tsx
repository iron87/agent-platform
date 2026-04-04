import type { ReactNode } from "react";
import type { ApiErrorView } from "../../lib/types";
import { FeedbackError, FeedbackLoading } from "./feedback";

interface OperationStateProps {
  loading: boolean;
  error: ApiErrorView | null;
  onRetry?: () => void;
  children: ReactNode;
}

export function OperationState({ loading, error, onRetry, children }: OperationStateProps) {
  if (loading) {
    return <FeedbackLoading message="Processing request..." />;
  }

  return (
    <div className="space-y-3">
      {error ? (
        <FeedbackError message={error.message} code={error.code} onRetry={onRetry} />
      ) : null}
      {children}
    </div>
  );
}
