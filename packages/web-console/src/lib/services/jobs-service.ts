import { apiRequest } from "../api-client";
import type { ConsoleProfile, JobStatus, JobSubmitRequest, JobSubmitResponse } from "../types";

export async function submitJob(profile: ConsoleProfile, request: JobSubmitRequest): Promise<JobSubmitResponse> {
  const payload = await apiRequest<any>({
    profile,
    path: "/jobs",
    method: "POST",
    body: JSON.stringify({
      agent_id: request.agentId,
      input: request.input,
      session_id: request.sessionId,
    }),
  });

  return {
    jobId: payload.job_id,
    status: payload.status,
  };
}

export async function getJobStatus(profile: ConsoleProfile, jobId: string): Promise<JobStatus> {
  const payload = await apiRequest<any>({
    profile,
    path: `/jobs/${jobId}`,
    method: "GET",
  });

  return {
    jobId: payload.job_id,
    status: payload.status,
    output: payload.output ?? null,
    error: payload.error ?? null,
    traceId: payload.trace_id ?? null,
    createdAt: payload.created_at,
    startedAt: payload.started_at ?? null,
    completedAt: payload.completed_at ?? null,
    pendingApprovalId: payload.pending_approval_id ?? null,
  };
}
