import type { ApprovalRequest } from "../../lib/types";
import { JsonViewer } from "../ui/json-viewer";

interface ApprovalDetailsPanelProps {
  approval: ApprovalRequest | null;
}

export function ApprovalDetailsPanel({ approval }: ApprovalDetailsPanelProps) {
  return (
    <section className="panel">
      <h3 className="panel-title mb-3">Approval Details</h3>
      {!approval ? (
        <p className="text-sm text-slate-600">No approval selected.</p>
      ) : (
        <div className="space-y-2 text-sm text-slate-800">
          <div><strong>ID:</strong> {approval.id}</div>
          <div><strong>Job:</strong> {approval.jobId}</div>
          <div><strong>Tool:</strong> {approval.toolName}</div>
          <div><strong>Status:</strong> {approval.status}</div>
          <div><strong>Timeout:</strong> {approval.timeoutAt}</div>
          {approval.contextSummary ? <div><strong>Context:</strong> {approval.contextSummary}</div> : null}
          <div className="pt-2">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Proposed Args</div>
            <JsonViewer data={approval.proposedArgs} />
          </div>
        </div>
      )}
    </section>
  );
}
