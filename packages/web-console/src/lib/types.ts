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
