import { apiRequest } from "../api-client";
import type { ApprovalDecisionInput, ApprovalRequest, ConsoleProfile } from "../types";

export async function getApproval(profile: ConsoleProfile, approvalId: string): Promise<ApprovalRequest> {
  const payload = await apiRequest<any>({
    profile,
    path: `/approvals/${approvalId}`,
    method: "GET",
  });

  return {
    id: payload.id,
    jobId: payload.job_id,
    toolName: payload.tool_name,
    proposedArgs: payload.proposed_args ?? {},
    contextSummary: payload.context_summary ?? null,
    status: payload.status,
    timeoutAt: payload.timeout_at,
    decisionAt: payload.decision_at ?? null,
    createdAt: payload.created_at,
  };
}

export async function decideApproval(
  profile: ConsoleProfile,
  approvalId: string,
  decision: ApprovalDecisionInput,
): Promise<ApprovalRequest> {
  const payload = await apiRequest<any>({
    profile,
    path: `/approvals/${approvalId}/decide`,
    method: "POST",
    body: JSON.stringify({
      approved: decision.approved,
      reviewer_id: decision.reviewerId,
      reason: decision.reason,
    }),
  });

  return {
    id: payload.id,
    jobId: payload.job_id,
    toolName: payload.tool_name,
    proposedArgs: payload.proposed_args ?? {},
    contextSummary: payload.context_summary ?? null,
    status: payload.status,
    timeoutAt: payload.timeout_at,
    decisionAt: payload.decision_at ?? null,
    createdAt: payload.created_at,
  };
}
