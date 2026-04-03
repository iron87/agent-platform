import { useState } from "react";
import type { ApiErrorView } from "../../lib/types";

interface ApprovalDecisionFormProps {
  approvalId: string | null;
  onApprove: (reviewerId: string, reason?: string) => Promise<void>;
  onReject: (reviewerId: string, reason?: string) => Promise<void>;
  loading?: boolean;
  error?: ApiErrorView | null;
}

export function ApprovalDecisionForm({
  approvalId,
  onApprove,
  onReject,
  loading = false,
  error = null,
}: ApprovalDecisionFormProps) {
  const [reviewerId, setReviewerId] = useState("operator-web");
  const [reason, setReason] = useState("");

  return (
    <section className="panel">
      <h3 className="panel-title mb-3">Approval Decision</h3>
      {!approvalId ? (
        <p className="text-sm text-slate-600">Select an approval to decide.</p>
      ) : (
        <div className="space-y-2">
          <input
            className="input-modern"
            value={reviewerId}
            onChange={(event) => setReviewerId(event.target.value)}
            placeholder="Reviewer ID"
          />
          <textarea
            className="input-modern min-h-20"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Reason (optional for approve, recommended for reject)"
          />
          {error ? <div className="text-sm text-rose-700">{error.message}</div> : null}
          <div className="flex gap-2">
            <button
              className="btn-primary"
              disabled={loading || !reviewerId.trim()}
              type="button"
              onClick={() => onApprove(reviewerId.trim(), reason || undefined)}
            >
              Approve
            </button>
            <button
              className="btn-secondary border-rose-300 text-rose-700 hover:bg-rose-50"
              disabled={loading || !reviewerId.trim()}
              type="button"
              onClick={() => onReject(reviewerId.trim(), reason || undefined)}
            >
              Reject
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
