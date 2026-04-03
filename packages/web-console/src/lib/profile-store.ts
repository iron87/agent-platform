import type { ConsoleProfile, ProfileState } from "./types";

const STORAGE_KEY = "two-brain.web-console.profiles.v1";
const BACKUP_KEY_PREFIX = "two-brain.web-console.profiles.v1.backup";

function emptyState(): ProfileState {
  return {
    activeProfileId: null,
    profiles: [],
  };
}

export function loadProfiles(): ProfileState {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return emptyState();
  }

  try {
    const parsed = JSON.parse(raw) as ProfileState;
    if (!parsed || !Array.isArray(parsed.profiles)) {
      throw new Error("Invalid storage payload");
    }
    return parsed;
  } catch {
    const backupKey = `${BACKUP_KEY_PREFIX}.${Date.now()}`;
    window.localStorage.setItem(backupKey, raw);
    window.localStorage.removeItem(STORAGE_KEY);
    return emptyState();
  }
}

export function saveProfiles(state: ProfileState): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function upsertProfile(
  state: ProfileState,
  profile: Omit<ConsoleProfile, "createdAt" | "updatedAt">,
): ProfileState {
  const now = new Date().toISOString();
  const existing = state.profiles.find((item) => item.id === profile.id);
  const normalized: ConsoleProfile = {
    ...profile,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };

  const profiles = state.profiles.some((item) => item.id === normalized.id)
    ? state.profiles.map((item) => (item.id === normalized.id ? normalized : item))
    : [normalized, ...state.profiles];

  return {
    activeProfileId: state.activeProfileId ?? normalized.id,
    profiles,
  };
}

export function deleteProfile(state: ProfileState, id: string): ProfileState {
  const profiles = state.profiles.filter((item) => item.id !== id);
  const activeProfileId = state.activeProfileId === id ? profiles[0]?.id ?? null : state.activeProfileId;
  return { activeProfileId, profiles };
}
