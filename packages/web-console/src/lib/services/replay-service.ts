import { apiRequest } from "../api-client";
import type { ConsoleProfile, ReplayRequest, RunResult } from "../types";

export async function replayRun(profile: ConsoleProfile, request: ReplayRequest): Promise<RunResult> {
  return apiRequest<RunResult>({
    profile,
    path: "/run/replay",
    method: "POST",
    body: JSON.stringify({
      trace_id: request.sourceRunId,
      agent_id: request.overrideAgentId,
      input: request.overrideInput,
    }),
  });
}
