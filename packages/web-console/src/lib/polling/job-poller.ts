import type { JobStatus } from "../types";

const DEFAULT_INTERVAL_MS = 2000;
const DEFAULT_TIMEOUT_MS = 300000;
const TERMINAL_STATES = new Set(["completed", "failed", "interrupted", "cancelled"]);

interface WatchOptions {
  intervalMs?: number;
  timeoutMs?: number;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function withRetry<T>(fn: () => Promise<T>, retries = 3): Promise<T> {
  let error: unknown;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await fn();
    } catch (e: any) {
      error = e;
      const code = String(e?.code ?? "").toUpperCase();
      if (code.startsWith("HTTP_4")) {
        throw e;
      }
      if (attempt < retries) {
        await sleep(2000 * (attempt + 1));
      }
    }
  }
  throw error;
}

export async function watchJob(
  fetchStatus: () => Promise<JobStatus>,
  onUpdate: (status: JobStatus, elapsedMs: number) => void,
  options: WatchOptions = {},
): Promise<JobStatus> {
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const started = Date.now();

  while (Date.now() - started <= timeoutMs) {
    const status = await withRetry(fetchStatus, 3);
    onUpdate(status, Date.now() - started);

    if (TERMINAL_STATES.has(String(status.status).toLowerCase())) {
      return status;
    }

    await sleep(intervalMs);
  }

  throw {
    code: "POLL_TIMEOUT",
    message: "Job polling timed out after 5 minutes",
  };
}
