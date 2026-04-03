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

function createDraft(mode: ProfileMode = "direct"): ProfileFormValue {
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
    <section className="panel">
      <h2 className="panel-title mb-3">Profiles</h2>

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
        <label className="flex flex-col gap-1 text-sm text-teal-900/85">
          Name
          <input
            className="input-modern"
            value={draft.name}
            onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="Production"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-teal-900/85">
          Base URL
          <input
            className="input-modern"
            value={draft.baseUrl}
            onChange={(event) => setDraft((prev) => ({ ...prev, baseUrl: event.target.value }))}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-teal-900/85">
          Mode
          <select
            className="input-modern"
            value={draft.mode}
            onChange={(event) => setDraft((prev) => ({ ...prev, mode: event.target.value as ProfileMode }))}
          >
            <option value="proxy">Proxy</option>
            <option value="direct">Direct</option>
          </select>
        </label>

        <ApiKeyField value={draft.apiKey} onChange={(apiKey) => setDraft((prev) => ({ ...prev, apiKey }))} />

        {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

        <button className="btn-primary" type="submit">
          Save profile
        </button>
      </form>

      <ul className="mt-4 space-y-2">
        {profiles.length === 0 ? <li className="text-sm text-teal-800/70">No profiles saved yet.</li> : null}
        {profiles.map((profile) => {
          const selected = profile.id === activeId;
          return (
            <li key={profile.id} className="rounded-xl border border-teal-100 bg-white p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium text-teal-950">{profile.name}</div>
                  <div className="text-xs text-teal-700/70">{profile.baseUrl}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    className={selected ? "btn-secondary bg-teal-50" : "btn-secondary"}
                    type="button"
                    onClick={() => onSelectProfile(profile.id)}
                  >
                    {selected ? "Active" : "Use"}
                  </button>
                  <button
                    className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50"
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
