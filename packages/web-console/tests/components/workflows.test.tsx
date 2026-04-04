import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReplayPanel } from "../../src/components/run/ReplayPanel";
import { RunPanel } from "../../src/components/run/RunPanel";
import type { ConsoleProfile } from "../../src/lib/types";
import { executeRun } from "../../src/lib/services/run-service";
import { replayRun } from "../../src/lib/services/replay-service";

vi.mock("../../src/lib/services/run-service", () => ({
  executeRun: vi.fn(),
}));

vi.mock("../../src/lib/services/replay-service", () => ({
  replayRun: vi.fn(),
}));

function sampleProfile(): ConsoleProfile {
  return {
    id: "p1",
    name: "Local",
    baseUrl: "http://localhost:8000",
    apiKey: "secret",
    mode: "direct",
    defaultAgentId: "",
    createdAt: "2026-04-01T10:00:00.000Z",
    updatedAt: "2026-04-01T10:00:00.000Z",
  };
}

describe("workflow panels", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows validation error when run fields are missing", async () => {
    render(<RunPanel profile={sampleProfile()} onOperation={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Execute run" }));

    expect(await screen.findByText("agentId and input are required")).toBeInTheDocument();
    expect(executeRun).not.toHaveBeenCalled();
  });

  it("executes run and records operation", async () => {
    const onOperation = vi.fn();
    vi.mocked(executeRun).mockResolvedValue({ status: "succeeded", output: { answer: "ok" } });

    render(<RunPanel profile={sampleProfile()} onOperation={onOperation} />);

    fireEvent.change(screen.getByPlaceholderText("Agent ID"), { target: { value: "agent-1" } });
    fireEvent.change(screen.getByPlaceholderText("Input"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Execute run" }));

    await waitFor(() => expect(executeRun).toHaveBeenCalledTimes(1));
    expect(onOperation).toHaveBeenCalledWith("run", true, expect.any(Object));
  });

  it("shows validation error for replay when fields are missing", async () => {
    render(<ReplayPanel profile={sampleProfile()} onOperation={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Execute replay" }));

    expect(await screen.findByText("traceId, overrideAgentId and overrideInput are required")).toBeInTheDocument();
    expect(replayRun).not.toHaveBeenCalled();
  });

  it("executes replay and records operation", async () => {
    const onOperation = vi.fn();
    vi.mocked(replayRun).mockResolvedValue({ status: "succeeded", output: { replay: true } });

    render(<ReplayPanel profile={sampleProfile()} onOperation={onOperation} />);

    fireEvent.change(screen.getByPlaceholderText("Trace ID"), { target: { value: "trace-1" } });
    fireEvent.change(screen.getByPlaceholderText("Override Agent ID"), { target: { value: "agent-1" } });
    fireEvent.change(screen.getByPlaceholderText("Override Input"), { target: { value: "retry" } });
    fireEvent.click(screen.getByRole("button", { name: "Execute replay" }));

    await waitFor(() => expect(replayRun).toHaveBeenCalledTimes(1));
    expect(onOperation).toHaveBeenCalledWith("replay", true, expect.any(Object));
  });
});
