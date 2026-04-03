import type { OperationResult } from "./types";

const MAX_RESULTS = 50;

export function appendOperationResult(
  current: OperationResult[],
  nextResult: OperationResult,
): OperationResult[] {
  // Keep newest entries first and preserve prior successful entries on failures.
  return [nextResult, ...current].slice(0, MAX_RESULTS);
}

export function createOperationResult(input: {
  name: string;
  success: boolean;
  payload?: unknown;
  error?: OperationResult["error"];
}): OperationResult {
  return {
    id: crypto.randomUUID(),
    name: input.name,
    createdAt: new Date().toISOString(),
    success: input.success,
    payload: input.payload,
    error: input.error,
  };
}
