import { useState } from "react";
import { ApprovalDecisionForm } from "../approvals/ApprovalDecisionForm";
import { ApprovalDetailsPanel } from "../approvals/ApprovalDetailsPanel";
import { JobApprovalLink } from "./JobApprovalLink";
import { decideApproval, getApproval } from "../../lib/services/approvals-service";
import { watchJob } from "../../lib/polling/job-poller";
import { getJobStatus, submitJob } from "../../lib/services/jobs-service";
import type { ApiErrorView, ApprovalRequest, ConsoleProfile, JobStatus } from "../../lib/types";
import { JsonViewer } from "../ui/json-viewer";

interface JobsPanelProps {
  profile: ConsoleProfile | null;
  onOperation: (name: string, success: boolean, payload?: unknown, error?: ApiErrorView) => void;
}

export function JobsPanel({ profile, onOperation }: JobsPanelProps) {
  const [agentId, setAgentId] = useState("");
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [watchElapsedMs, setWatchElapsedMs] = useState(0);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorView | null>(null);
  const [approvalError, setApprovalError] = useState<ApiErrorView | null>(null);

  const submit = async () => {
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
      const created = await submitJob(profile, {
        agentId: agentId.trim(),
        input,
        sessionId: sessionId.trim() || undefined,
      });
      setJobId(created.jobId);
      setError(null);
      onOperation("jobs.submit", true, created);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("jobs.submit", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    if (!profile || !jobId.trim()) {
      setError({ code: "VALIDATION", message: "jobId is required" });
      return;
    }

    setLoading(true);
    try {
      const status = await getJobStatus(profile, jobId.trim());
      setJobStatus(status);
      setError(null);
      onOperation("jobs.status", true, status);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("jobs.status", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  const watch = async () => {
    if (!profile || !jobId.trim()) {
      setError({ code: "VALIDATION", message: "jobId is required" });
      return;
    }

    setLoading(true);
    try {
      const finalStatus = await watchJob(
        () => getJobStatus(profile, jobId.trim()),
        (status, elapsedMs) => {
          setJobStatus(status);
          setWatchElapsedMs(elapsedMs);
        },
      );
      setError(null);
      onOperation("jobs.watch", true, finalStatus);
    } catch (e) {
      const err = e as ApiErrorView;
      setError(err);
      onOperation("jobs.watch", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  const openApproval = async (approvalId: string) => {
    if (!profile) {
      setApprovalError({ code: "PROFILE_REQUIRED", message: "Select a profile first" });
      return;
    }

    setLoading(true);
    try {
      const payload = await getApproval(profile, approvalId);
      setApproval(payload);
      setApprovalError(null);
      onOperation("approvals.get", true, payload);
    } catch (e) {
      const err = e as ApiErrorView;
      setApprovalError(err);
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
      const updated = await decideApproval(profile, approval.id, {
        approved: true,
        reviewerId,
        reason,
      });
      setApproval(updated);
      setApprovalError(null);
      onOperation("approvals.decide", true, updated);
    } catch (e) {
      const err = e as ApiErrorView;
      setApprovalError(err);
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
      const updated = await decideApproval(profile, approval.id, {
        approved: false,
        reviewerId,
        reason,
      });
      setApproval(updated);
      setApprovalError(null);
      onOperation("approvals.decide", true, updated);
    } catch (e) {
      const err = e as ApiErrorView;
      setApprovalError(err);
      onOperation("approvals.decide", false, undefined, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-4">
      <section className="panel">
        <h2 className="panel-title mb-3">Jobs</h2>
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
            className="input-modern min-h-28 md:col-span-2"
            placeholder="Job input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button className="btn-primary" type="button" disabled={loading} onClick={submit}>
            Submit Job
          </button>
        </div>

        <div className="mt-4 grid gap-2 md:grid-cols-[1fr_auto_auto]">
          <input
            className="input-modern"
            placeholder="Job ID"
            value={jobId}
            onChange={(event) => setJobId(event.target.value)}
          />
          <button className="btn-secondary" type="button" disabled={loading} onClick={fetchStatus}>
            Fetch Status
          </button>
          <button className="btn-secondary" type="button" disabled={loading} onClick={watch}>
            Watch (2s)
          </button>
        </div>

        {watchElapsedMs > 0 ? (
          <div className="mt-2 text-xs text-slate-600">Watch elapsed: {(watchElapsedMs / 1000).toFixed(1)}s</div>
        ) : null}

        {error ? <div className="mt-3 text-sm text-rose-700">{error.message}</div> : null}

        {jobStatus ? (
          <div className="mt-4 space-y-3">
            <JobApprovalLink pendingApprovalId={jobStatus.pendingApprovalId} onOpenApproval={openApproval} />
            <JsonViewer data={jobStatus} />
          </div>
        ) : null}
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <ApprovalDetailsPanel approval={approval} />
        <ApprovalDecisionForm
          approvalId={approval?.id ?? null}
          loading={loading}
          error={approvalError}
          onApprove={approve}
          onReject={reject}
        />
      </div>
    </section>
  );
}
