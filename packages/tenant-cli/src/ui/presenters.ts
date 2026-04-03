import type {ApprovalRequest, JobStatus, RunResponse} from '../api/client.js';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function hasKeys(value: unknown, keys: string[]): boolean {
  if (!isRecord(value)) {
    return false;
  }
  return keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}

function formatRunResponse(value: RunResponse): string {
  const lines = [
    `job_id: ${value.job_id}`,
    `status: ${value.status ?? 'completed'}`,
    `trace_id: ${value.trace_id ?? 'null'}`,
  ];

  if (value.session_id) {
    lines.push(`session_id: ${value.session_id}`);
  }
  if (value.pending_approval_id) {
    lines.push(`pending_approval_id: ${value.pending_approval_id}`);
  }
  lines.push('output:');
  lines.push(value.output);
  return lines.join('\n');
}

function formatJobStatus(value: JobStatus): string {
  const lines = [
    `job_id: ${value.job_id}`,
    `status: ${value.status}`,
    `trace_id: ${value.trace_id ?? 'null'}`,
    `created_at: ${value.created_at}`,
    `started_at: ${value.started_at ?? 'null'}`,
    `completed_at: ${value.completed_at ?? 'null'}`,
  ];

  if (value.pending_approval_id) {
    lines.push(`pending_approval_id: ${value.pending_approval_id}`);
  }
  if (value.output) {
    lines.push('output:');
    lines.push(value.output);
  }
  if (value.error) {
    lines.push('error:');
    lines.push(value.error);
  }
  return lines.join('\n');
}

function formatApprovalRequest(value: ApprovalRequest): string {
  const lines = [
    `approval_id: ${value.id}`,
    `job_id: ${value.job_id}`,
    `status: ${value.status}`,
    `tool_name: ${value.tool_name}`,
    `timeout_at: ${value.timeout_at}`,
    `decision_at: ${value.decision_at ?? 'null'}`,
  ];

  if (value.context_summary) {
    lines.push(`context_summary: ${value.context_summary}`);
  }

  lines.push('proposed_args:');
  lines.push(JSON.stringify(value.proposed_args, null, 2));
  return lines.join('\n');
}

export function renderText(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }

  if (hasKeys(value, ['job_id', 'output', 'trace_id'])) {
    return formatRunResponse(value as RunResponse);
  }

  if (hasKeys(value, ['job_id', 'status', 'created_at'])) {
    return formatJobStatus(value as JobStatus);
  }

  if (hasKeys(value, ['id', 'job_id', 'tool_name', 'proposed_args', 'timeout_at'])) {
    return formatApprovalRequest(value as ApprovalRequest);
  }

  return JSON.stringify(value, null, 2);
}
