import { apiRequest } from "../api-client";
import type { ConsoleProfile, SessionMessage } from "../types";

interface SendSessionMessageInput {
  agentId: string;
  sessionId: string;
  content: string;
}

export async function sendSessionMessage(
  profile: ConsoleProfile,
  input: SendSessionMessageInput,
): Promise<SessionMessage> {
  const payload = await apiRequest<any>({
    profile,
    path: "/run",
    method: "POST",
    body: JSON.stringify({
      agent_id: input.agentId,
      input: input.content,
      session_id: input.sessionId,
    }),
  });

  return {
    messageId: payload.job_id ?? payload.id,
    sessionId: payload.session_id ?? input.sessionId,
    role: "assistant",
    content: payload.output ?? "",
    createdAt: payload.created_at ?? payload.createdAt,
    traceId: payload.trace_id,
    status: payload.status,
    pendingApprovalId: payload.pending_approval_id ?? null,
  };
}
