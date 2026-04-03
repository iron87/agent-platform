import { apiRequest } from "../api-client";
import type { ConsoleProfile, RunRequest, RunResult } from "../types";

export async function executeRun(profile: ConsoleProfile, request: RunRequest): Promise<RunResult> {
  return apiRequest<RunResult>({
    profile,
    path: "/run",
    method: "POST",
    body: JSON.stringify({
      agent_id: request.agentId,
      input: request.input,
      session_id: request.sessionId,
    }),
  });
}
