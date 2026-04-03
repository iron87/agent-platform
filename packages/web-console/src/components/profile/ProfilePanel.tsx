import { useMemo, useState } from "react";
import type { ConsoleProfile, ProfileMode } from "../../lib/types";
import { ApiKeyField } from "./ApiKeyField";
import { createProfileFromForm, type ProfileFormValue, validateProfile } from "./profile-validation";

interface ProfilePanelProps {
  profiles: ConsoleProfile[];
  activeProfileId: string | null;
  onSaveProfile: (profile: Omit<ConsoleProfile, "createdAt" | "updatedAt">) => void;
  onDeleteProfile: (profileId: string) => void;
  onSelectProfile: (profileId: string) => void;
}

function createDraft(mode: ProfileMode = "proxy"): ProfileFormValue {
  return {
    id: crypto.randomUUID(),
    name: "",
    baseUrl: "http://localhost:8000",
    apiKey: "",
    mode,
    defaultAgentId: "",
  };
}

export function ProfilePanel({
  profiles,
  activeProfileId,
  onSaveProfile,
  onDeleteProfile,
  onSelectProfile,
}: ProfilePanelProps) {
  const [draft, setDraft] = useState<ProfileFormValue>(() => createDraft());
  const [error, setError] = useState<string | null>(null);

  const activeId = useMemo(() => activeProfileId ?? profiles[0]?.id ?? null, [activeProfileId, profiles]);

  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <h2 className="mb-3 text-base font-semibold">Profiles</h2>

      <form
        className="grid gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const validation = validateProfile(draft);
          if (!validation.ok) {
            setError(validation.message);
            return;
          }
          onSaveProfile(createProfileFromForm(draft));
          setError(null);
          setDraft(createDraft(draft.mode));
        }}
      >
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Name
          <input
            className="rounded-md border border-slate-300 px-3 py-2"
            value={draft.name}
            onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="Production"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Base URL
          <input
            className="rounded-md border border-slate-300 px-3 py-2"
            value={draft.baseUrl}
            onChange={(event) => setDraft((prev) => ({ ...prev, baseUrl: event.target.value }))}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Mode
          <select
            className="rounded-md border border-slate-300 px-3 py-2"
            value={draft.mode}
            onChange={(event) => setDraft((prev) => ({ ...prev, mode: event.target.value as ProfileMode }))}
          >
            <option value="proxy">Proxy</option>
            <option value="direct">Direct</option>
          </select>
        </label>

        <ApiKeyField value={draft.apiKey} onChange={(apiKey) => setDraft((prev) => ({ ...prev, apiKey }))} />

        {error ? <div className="text-sm text-red-700">{error}</div> : null}

        <button className="rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white" type="submit">
          Save profile
        </button>
      </form>

      <ul className="mt-4 space-y-2">
        {profiles.length === 0 ? <li className="text-sm text-slate-500">No profiles saved yet.</li> : null}
        {profiles.map((profile) => {
          const selected = profile.id === activeId;
          return (
            <li key={profile.id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{profile.name}</div>
                  <div className="text-xs text-slate-500">{profile.baseUrl}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    className="rounded border border-slate-300 px-2 py-1"
                    type="button"
                    onClick={() => onSelectProfile(profile.id)}
                  >
                    {selected ? "Active" : "Use"}
                  </button>
                  <button
                    className="rounded border border-red-300 px-2 py-1 text-red-700"
                    type="button"
                    onClick={() => onDeleteProfile(profile.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
