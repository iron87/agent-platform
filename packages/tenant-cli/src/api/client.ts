export interface RunRequest {
  agent_id: string;
  input: string;
  session_id?: string;
  metadata?: Record<string, unknown>;
}

export interface RunResponse {
  job_id: string;
  output: string;
  trace_id: string | null;
  session_id: string | null;
}

export interface JobSubmitRequest {
  agent_id: string;
  input: string;
  session_id?: string;
  metadata?: Record<string, unknown>;
}

export interface JobSubmitResponse {
  job_id: string;
  status: 'pending';
}

export type JobState = 'pending' | 'running' | 'interrupted' | 'completed' | 'failed';

export interface JobStatus {
  job_id: string;
  status: JobState;
  output: string | null;
  error: string | null;
  trace_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  pending_approval_id: string | null;
}

export interface ApprovalDecision {
  approved: boolean;
  reason?: string;
  reviewer_id: string;
}

export interface ApprovalRequest {
  id: string;
  job_id: string;
  tool_name: string;
  proposed_args: Record<string, unknown>;
  context_summary: string | null;
  status: string;
  timeout_at: string;
  decision_at: string | null;
  created_at: string;
}

export interface AgentSummary {
  id: string;
  name: string;
  graph_type: 'conversational' | 'tool_agent' | 'batch_agent';
  model_alias: 'default' | 'fast' | 'embedding';
  version: number;
  semantic_memory_enabled: boolean;
}

export interface AgentListResponse {
  agents: AgentSummary[];
}

export interface AgentCreateRequest {
  name: string;
  prompt_file: string;
  model_alias?: 'default' | 'fast' | 'embedding';
  max_execution_seconds?: number;
  semantic_memory_enabled?: boolean;
}

export interface AgentCreateResponse {
  agent: AgentSummary;
}

const TERMINAL_STATES: ReadonlySet<JobState> = new Set([
  'completed',
  'failed',
  'interrupted',
]);

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`HTTP ${status}: ${detail}`);
  }
}

async function apiRequest<T>(
  baseUrl: string,
  apiKey: string,
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${baseUrl.replace(/\/$/, '')}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
  };

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    data = {detail: text};
  }

  if (!response.ok) {
    const detail =
      typeof data === 'object' && data !== null && 'detail' in data
        ? String((data as {detail: unknown}).detail)
        : `HTTP ${response.status}`;
    throw new ApiError(response.status, detail);
  }

  return data as T;
}

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
  ) {}

  async run(req: RunRequest): Promise<RunResponse> {
    return apiRequest<RunResponse>(this.baseUrl, this.apiKey, 'POST', '/run', req);
  }

  async submitJob(req: JobSubmitRequest): Promise<JobSubmitResponse> {
    return apiRequest<JobSubmitResponse>(this.baseUrl, this.apiKey, 'POST', '/jobs', req);
  }

  async getJob(jobId: string): Promise<JobStatus> {
    return apiRequest<JobStatus>(this.baseUrl, this.apiKey, 'GET', `/jobs/${jobId}`);
  }

  async waitForJob(
    jobId: string,
    pollIntervalSeconds: number,
    timeoutSeconds = 300,
  ): Promise<JobStatus> {
    const deadline = Date.now() + timeoutSeconds * 1000;
    while (Date.now() < deadline) {
      const status = await this.getJob(jobId);
      if (TERMINAL_STATES.has(status.status)) {
        return status;
      }
      await new Promise<void>((resolve) =>
        setTimeout(resolve, pollIntervalSeconds * 1000),
      );
    }
    throw new Error(`Job ${jobId} did not reach terminal state within ${timeoutSeconds}s`);
  }

  async getApproval(approvalId: string): Promise<ApprovalRequest> {
    return apiRequest<ApprovalRequest>(
      this.baseUrl,
      this.apiKey,
      'GET',
      `/approvals/${approvalId}`,
    );
  }

  async decideApproval(approvalId: string, decision: ApprovalDecision): Promise<unknown> {
    return apiRequest<unknown>(
      this.baseUrl,
      this.apiKey,
      'POST',
      `/approvals/${approvalId}/decide`,
      decision,
    );
  }

  async listAgents(): Promise<AgentListResponse> {
    return apiRequest<AgentListResponse>(this.baseUrl, this.apiKey, 'GET', '/agents');
  }

  async createAgent(req: AgentCreateRequest): Promise<AgentCreateResponse> {
    return apiRequest<AgentCreateResponse>(this.baseUrl, this.apiKey, 'POST', '/agents', req);
  }
}
