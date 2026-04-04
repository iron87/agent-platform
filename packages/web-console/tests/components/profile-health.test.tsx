import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HealthPanel } from "../../src/components/health/HealthPanel";
import { ProfilePanel } from "../../src/components/profile/ProfilePanel";
import type { ConsoleProfile } from "../../src/lib/types";

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

describe("profile + health panels", () => {
  it("submits profile form with valid values", () => {
    const onSaveProfile = vi.fn();

    render(
      <ProfilePanel
        profiles={[]}
        activeProfileId={null}
        onSaveProfile={onSaveProfile}
        onDeleteProfile={vi.fn()}
        onSelectProfile={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Production"), { target: { value: "Dev" } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "http://localhost:8000" } });
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "abc123" } });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    expect(onSaveProfile).toHaveBeenCalledTimes(1);
    expect(onSaveProfile.mock.calls[0][0]).toMatchObject({
      name: "Dev",
      baseUrl: "http://localhost:8000",
      apiKey: "abc123",
      mode: "direct",
    });
  });

  it("runs health check and shows latest payload", async () => {
    const onRun = vi.fn().mockResolvedValue(undefined);

    render(
      <HealthPanel
        onRun={onRun}
        latestPayload={{ status: "ok", dependencies: [{ name: "db", ok: true }] }}
        latestError={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Run health check" }));

    await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Latest response")).toBeInTheDocument();
    expect(screen.getByText(/\"status\": \"ok\"/)).toBeInTheDocument();
  });

  it("renders API error details when provided", () => {
    render(
      <HealthPanel onRun={vi.fn()} latestPayload={null} latestError={{ code: "ERR", message: "Boom", traceId: "trace-1" }} />,
    );

    expect(screen.getByText("Boom")).toBeInTheDocument();
    expect(screen.getByText("Trace: trace-1")).toBeInTheDocument();
  });

  it("shows saved profile list and active state", () => {
    render(
      <ProfilePanel
        profiles={[sampleProfile()]}
        activeProfileId="p1"
        onSaveProfile={vi.fn()}
        onDeleteProfile={vi.fn()}
        onSelectProfile={vi.fn()}
      />,
    );

    expect(screen.getByText("Local")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Active" })).toBeInTheDocument();
  });
});
