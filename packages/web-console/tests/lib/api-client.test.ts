import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../../src/lib/api-client";
import type { ConsoleProfile } from "../../src/lib/types";

function makeProfile(overrides?: Partial<ConsoleProfile>): ConsoleProfile {
  return {
    id: "p1",
    name: "Local",
    baseUrl: "http://localhost:8000",
    apiKey: "test-key",
    mode: "direct",
    createdAt: "2026-04-01T10:00:00.000Z",
    updatedAt: "2026-04-01T10:00:00.000Z",
    ...overrides,
  };
}

describe("api-client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses /api/v1 suffix and direct auth headers", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await apiRequest<{ ok: boolean }>({
      profile: makeProfile({ mode: "direct" }),
      path: "/health",
      method: "GET",
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/health");

    const headers = init?.headers as Headers;
    expect(headers.get("X-API-Key")).toBe("test-key");
    expect(headers.get("Authorization")).toBe("Bearer test-key");
  });

  it("avoids duplicating /api/v1 when baseUrl already includes it", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await apiRequest<{ ok: boolean }>({
      profile: makeProfile({ mode: "direct", baseUrl: "http://localhost:8000/api/v1" }),
      path: "/health",
      method: "GET",
    });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/health");
  });

  it("uses proxy base path in proxy mode and omits bearer header", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await apiRequest<{ ok: boolean }>({
      profile: makeProfile({ mode: "proxy" }),
      path: "/health",
      method: "GET",
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/health");

    const headers = init?.headers as Headers;
    expect(headers.get("X-API-Key")).toBe("test-key");
    expect(headers.get("Authorization")).toBeNull();
  });
});
