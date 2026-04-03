import { useMemo, useState } from "react";
import { HealthPanel } from "../components/health/HealthPanel";
import { ActiveProfileBanner } from "../components/profile/ActiveProfileBanner";
import { ProfilePanel } from "../components/profile/ProfilePanel";
import { JsonViewer } from "../components/ui/json-viewer";
import { useAppState } from "./AppStateProvider";

const modules = ["health", "agents", "run", "session", "jobs", "approvals"] as const;

type ModuleKey = (typeof modules)[number];

export function AppLayout() {
  const [activeModule, setActiveModule] = useState<ModuleKey>("health");
  const { activeProfile, profileState, operations, runHealthCheck, saveProfile, removeProfile, selectProfile } = useAppState();

  const latestHealth = useMemo(
    () => operations.find((operation) => operation.name === "health") ?? null,
    [operations],
  );

  const mainContent =
    activeModule === "health" ? (
      <HealthPanel
        onRun={runHealthCheck}
        latestPayload={(latestHealth?.payload as any) ?? null}
        latestError={latestHealth?.error ?? null}
      />
    ) : (
      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <h2 className="text-base font-semibold capitalize">{activeModule}</h2>
        <p className="mt-2 text-sm text-slate-600">This module is planned in later phases.</p>
      </section>
    );

  return (
    <div className="min-h-screen bg-gradient-to-b from-cyan-50 to-white p-4 md:p-6">
      <div className="mx-auto grid max-w-7xl gap-4 lg:grid-cols-[340px_1fr_420px]">
        <aside className="space-y-4">
          <ActiveProfileBanner profile={activeProfile} />
          <ProfilePanel
            profiles={profileState.profiles}
            activeProfileId={profileState.activeProfileId}
            onSaveProfile={saveProfile}
            onDeleteProfile={removeProfile}
            onSelectProfile={selectProfile}
          />
        </aside>

        <main className="space-y-4">
          <nav className="flex flex-wrap gap-2">
            {modules.map((module) => (
              <button
                key={module}
                type="button"
                className={`rounded-md border px-3 py-2 text-sm font-medium capitalize ${
                  activeModule === module
                    ? "border-sky-500 bg-sky-100 text-sky-900"
                    : "border-slate-300 bg-white text-slate-700"
                }`}
                onClick={() => setActiveModule(module)}
              >
                {module}
              </button>
            ))}
          </nav>
          {mainContent}
        </main>

        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="mb-3 text-base font-semibold">Operation history</h2>
          {operations.length === 0 ? (
            <p className="text-sm text-slate-500">No operations yet.</p>
          ) : (
            <div className="space-y-3">
              {operations.map((operation) => (
                <article key={operation.id} className="rounded-md border border-slate-200 p-3">
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="font-medium capitalize">{operation.name}</span>
                    <span className={operation.success ? "text-emerald-700" : "text-red-700"}>
                      {operation.success ? "Success" : "Failed"}
                    </span>
                  </div>
                  <div className="mb-2 text-xs text-slate-500">{operation.createdAt}</div>
                  <JsonViewer data={operation.success ? operation.payload : operation.error} />
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
