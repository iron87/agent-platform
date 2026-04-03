import { useState } from "react";
import { decideApproval, getApproval } from "../../lib/services/approvals-service";
import type { ApiErrorView, ApprovalRequest, ConsoleProfile } from "../../lib/types";
import { ApprovalDecisionForm } from "./ApprovalDecisionForm";
import { ApprovalDetailsPanel } from "./ApprovalDetailsPanel";

interface ApprovalsPanelProps {
  profile: ConsoleProfile | null;
  onOperation: (name: string, success: boolean, payload?: unknown, error?: ApiErrorView) => void;
}

export function ApprovalsPanel({ profile, onOperation }: ApprovalsPanelProps) {
  const [approvalId, setApprovalId] = useState("");
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorView | null>(null);

  const openApproval = async () => {
    if (!profile) {
      setError({ code: "PROFILE_REQUIRED", message: "Select a profile first" });
      return;
    }
    if (!approvalId.trim()) {
      setError({ code: "VALIDATION", message: "Approval ID is required" });
      return;
    }

    setLoading(true);
    try {
      const payload = await getApproval(profile, approvalId.trim());
      setApproval(payload);
      setError(null);
      onOperation("approvals.get", true, payload);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("approvals.get", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  const approve = async (reviewerId: string, reason?: string) => {
    if (!profile || !approval) {
      return;
    }

    setLoading(true);
    try {
      const payload = await decideApproval(profile, approval.id, {
        approved: true,
        reviewerId,
        reason,
      });
      setApproval(payload);
      setError(null);
      onOperation("approvals.decide", true, payload);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("approvals.decide", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  const reject = async (reviewerId: string, reason?: string) => {
    if (!profile || !approval) {
      return;
    }

    setLoading(true);
    try {
      const payload = await decideApproval(profile, approval.id, {
        approved: false,
        reviewerId,
        reason,
      });
      setApproval(payload);
      setError(null);
      onOperation("approvals.decide", true, payload);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("approvals.decide", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-4">
      <section className="panel">
        <h2 className="panel-title mb-3">Approvals</h2>
        <div className="grid gap-2 md:grid-cols-[1fr_auto]">
          <input
            className="input-modern"
            placeholder="Approval ID"
            value={approvalId}
            onChange={(event) => setApprovalId(event.target.value)}
          />
          <button className="btn-secondary" type="button" onClick={openApproval} disabled={loading}>
            Open
          </button>
        </div>
        {error ? <div className="mt-2 text-sm text-rose-700">{error.message}</div> : null}
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <ApprovalDetailsPanel approval={approval} />
        <ApprovalDecisionForm
          approvalId={approval?.id ?? null}
          loading={loading}
          error={error}
          onApprove={approve}
          onReject={reject}
        />
      </div>
    </section>
  );
}
