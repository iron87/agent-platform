import { beforeEach, describe, expect, it } from "vitest";
import { deleteProfile, loadProfiles, saveProfiles, upsertProfile } from "../../src/lib/profile-store";
import type { ProfileState } from "../../src/lib/types";

const STORAGE_KEY = "two-brain.web-console.profiles.v1";

describe("profile-store", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns empty state when nothing is stored", () => {
    expect(loadProfiles()).toEqual({
      activeProfileId: null,
      profiles: [],
    });
  });

  it("backs up malformed payload and resets state", () => {
    window.localStorage.setItem(STORAGE_KEY, "{bad-json");

    const loaded = loadProfiles();

    expect(loaded).toEqual({ activeProfileId: null, profiles: [] });
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();

    const backupKeys = Object.keys(window.localStorage).filter((key) =>
      key.startsWith("two-brain.web-console.profiles.v1.backup."),
    );
    expect(backupKeys).toHaveLength(1);
    expect(window.localStorage.getItem(backupKeys[0])).toBe("{bad-json");
  });

  it("upserts profile and preserves createdAt across updates", () => {
    const initial: ProfileState = { activeProfileId: null, profiles: [] };

    const first = upsertProfile(initial, {
      id: "p1",
      name: "Local",
      baseUrl: "http://localhost:8000",
      apiKey: "secret",
      mode: "direct",
      defaultAgentId: "",
    });

    const second = upsertProfile(first, {
      id: "p1",
      name: "Local Updated",
      baseUrl: "http://localhost:8000",
      apiKey: "secret-2",
      mode: "direct",
      defaultAgentId: "",
    });

    expect(second.activeProfileId).toBe("p1");
    expect(second.profiles).toHaveLength(1);
    expect(second.profiles[0].createdAt).toBe(first.profiles[0].createdAt);
    expect(second.profiles[0].updatedAt >= second.profiles[0].createdAt).toBe(true);
    expect(second.profiles[0].name).toBe("Local Updated");
  });

  it("deletes active profile and selects next available", () => {
    const state: ProfileState = {
      activeProfileId: "p1",
      profiles: [
        {
          id: "p1",
          name: "First",
          baseUrl: "http://localhost:8000",
          apiKey: "k1",
          mode: "direct",
          defaultAgentId: "",
          createdAt: "2026-04-01T10:00:00.000Z",
          updatedAt: "2026-04-01T10:00:00.000Z",
        },
        {
          id: "p2",
          name: "Second",
          baseUrl: "http://localhost:8000",
          apiKey: "k2",
          mode: "proxy",
          defaultAgentId: "",
          createdAt: "2026-04-01T10:01:00.000Z",
          updatedAt: "2026-04-01T10:01:00.000Z",
        },
      ],
    };

    const next = deleteProfile(state, "p1");
    expect(next.activeProfileId).toBe("p2");
    expect(next.profiles).toHaveLength(1);

    saveProfiles(next);
    expect(loadProfiles()).toEqual(next);
  });
});
