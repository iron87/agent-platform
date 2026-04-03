export type ProfileMode = "proxy" | "direct";

export interface ConsoleProfile {
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  mode: ProfileMode;
  defaultAgentId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProfileState {
  activeProfileId: string | null;
  profiles: ConsoleProfile[];
}

export interface HealthDependency {
  name: string;
  ok: boolean;
  detail?: string;
}

export interface HealthResponse {
  status: string;
  dependencies?: HealthDependency[];
  [key: string]: unknown;
}

export interface ApiErrorView {
  code: string;
  message: string;
  details?: unknown;
  traceId?: string;
}

export interface OperationResult {
  id: string;
  name: string;
  createdAt: string;
  success: boolean;
  payload?: unknown;
  error?: ApiErrorView;
}

export interface RequestState<TData = unknown> {
  loading: boolean;
  data: TData | null;
  error: ApiErrorView | null;
}

export interface AgentSummary {
  agentId: string;
  name: string;
  description?: string;
  createdAt?: string;
  graphType?: "conversational" | "tool_agent" | "batch_agent";
  modelAlias?: "default" | "fast" | "embedding";
  version?: number;
  semanticMemoryEnabled?: boolean;
}

export interface AgentCreateInput {
  name: string;
  promptFile: string;
  modelAlias?: "default" | "fast" | "embedding";
  maxExecutionSeconds?: number;
  semanticMemoryEnabled?: boolean;
}

export interface RunRequest {
  agentId: string;
  input: string;
  sessionId?: string;
}

export interface RunResult {
  runId?: string;
  jobId?: string;
  traceId?: string;
  status?: string;
  output?: unknown;
  [key: string]: unknown;
}

export interface JobSubmitRequest {
  agentId: string;
  input: string;
  sessionId?: string;
}

export interface JobSubmitResponse {
  jobId: string;
  status: "pending" | string;
}

export type JobState = "pending" | "running" | "interrupted" | "completed" | "failed";

export interface JobStatus {
  jobId: string;
  status: JobState | string;
  output: string | null;
  error: string | null;
  traceId: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  pendingApprovalId: string | null;
}

export interface ApprovalDecisionInput {
  approved: boolean;
  reviewerId: string;
  reason?: string;
}

export interface ApprovalRequest {
  id: string;
  jobId: string;
  toolName: string;
  proposedArgs: Record<string, unknown>;
  contextSummary: string | null;
  status: string;
  timeoutAt: string;
  decisionAt: string | null;
  createdAt: string;
}

export interface ReplayRequest {
  sourceRunId: string;
  overrideInput?: string;
  overrideAgentId?: string;
}

export interface SessionMessage {
  messageId?: string;
  sessionId: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  createdAt?: string;
  traceId?: string;
  status?: string;
  pendingApprovalId?: string | null;
}

export interface ConversationItem {
  id: string;
  profileId: string;
  agentId: string;
  sessionId: string;
  title: string;
  updatedAt: string;
  messages: SessionMessage[];
}
