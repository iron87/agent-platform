import type { ApiErrorView } from "./types";

export function extractTraceId(headers?: Headers): string | undefined {
  if (!headers) {
    return undefined;
  }

  return headers.get("x-trace-id") ?? headers.get("trace-id") ?? undefined;
}

export async function normalizeError(
  response: Response,
  fallbackMessage = "Request failed",
): Promise<ApiErrorView> {
  let body: any = null;

  try {
    body = await response.clone().json();
  } catch {
    try {
      body = await response.text();
    } catch {
      body = null;
    }
  }

  const traceId = extractTraceId(response.headers);
  const code = typeof body?.code === "string" ? body.code : `HTTP_${response.status}`;
  const message =
    typeof body?.message === "string"
      ? body.message
      : typeof body?.detail === "string"
        ? body.detail
        : fallbackMessage;

  return {
    code,
    message,
    details: body,
    traceId,
  };
}
