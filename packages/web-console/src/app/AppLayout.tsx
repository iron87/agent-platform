import { useEffect, useMemo, useRef, useState } from "react";
import { AgentsPanel } from "../components/agents/AgentsPanel";
import { ApprovalsPanel } from "../components/approvals/ApprovalsPanel";
import { FeedbackEmpty, useFeedback } from "../components/shared/feedback";
import { HealthPanel } from "../components/health/HealthPanel";
import { JobsPanel } from "../components/jobs/JobsPanel";
import { ActiveProfileBanner } from "../components/profile/ActiveProfileBanner";
import { ProfilePanel } from "../components/profile/ProfilePanel";
import { ReplayPanel } from "../components/run/ReplayPanel";
import { RunPanel } from "../components/run/RunPanel";
import { SessionPanel } from "../components/session/SessionPanel";
import { JsonViewer } from "../components/ui/json-viewer";
import { useAppState } from "./AppStateProvider";

const modules = ["health", "agents", "run", "session", "jobs", "approvals"] as const;

type ModuleKey = (typeof modules)[number];

export function AppLayout() {
  const [activeModule, setActiveModule] = useState<ModuleKey>("health");
  const { pushToast } = useFeedback();
  const lastToastOperationRef = useRef<string | null>(null);
  const {
    activeProfile,
    profileState,
    operations,
    recordOperation,
    runHealthCheck,
    saveProfile,
    removeProfile,
    selectProfile,
  } = useAppState();

  const latestHealth = useMemo(
    () => operations.find((operation) => operation.name === "health") ?? null,
    [operations],
  );

  useEffect(() => {
    const latest = operations[0];
    if (!latest || latest.id === lastToastOperationRef.current) {
      return;
    }

    lastToastOperationRef.current = latest.id;
    pushToast(
      `${latest.name}: ${latest.success ? "completed" : "failed"}`,
      latest.success ? "success" : "error",
    );
  }, [operations, pushToast]);

  let mainContent: JSX.Element;

  if (activeModule === "health") {
    mainContent = (
      <HealthPanel
        onRun={runHealthCheck}
        latestPayload={(latestHealth?.payload as any) ?? null}
        latestError={latestHealth?.error ?? null}
      />
    );
  } else if (activeModule === "agents") {
    mainContent = <AgentsPanel profile={activeProfile} onOperation={recordOperation} />;
  } else if (activeModule === "run") {
    mainContent = (
      <div className="space-y-4">
        <RunPanel profile={activeProfile} onOperation={recordOperation} />
        <ReplayPanel profile={activeProfile} onOperation={recordOperation} />
      </div>
    );
  } else if (activeModule === "session") {
    mainContent = <SessionPanel profile={activeProfile} onOperation={recordOperation} />;
  } else if (activeModule === "jobs") {
    mainContent = <JobsPanel profile={activeProfile} onOperation={recordOperation} />;
  } else if (activeModule === "approvals") {
    mainContent = <ApprovalsPanel profile={activeProfile} onOperation={recordOperation} />;
  } else {
    mainContent = (
      <section className="panel">
        <h2 className="panel-title capitalize">{activeModule}</h2>
        <p className="mt-2 text-sm text-slate-600">This module is planned in later phases.</p>
      </section>
    );
  }

  return (
    <div className="min-h-screen px-4 py-4 md:px-6 md:py-5">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:rounded focus:bg-white focus:px-2 focus:py-1">
        Skip to main content
      </a>
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(760px,1fr)_420px]">
        <aside className="space-y-4 xl:sticky xl:top-4 xl:h-fit">
          <ActiveProfileBanner profile={activeProfile} />
          <ProfilePanel
            profiles={profileState.profiles}
            activeProfileId={profileState.activeProfileId}
            onSaveProfile={saveProfile}
            onDeleteProfile={removeProfile}
            onSelectProfile={selectProfile}
          />
        </aside>

        <main id="main-content" className="space-y-4" role="main">
          <header className="panel">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">2brain Operator Console</h1>
                <p className="mt-1 text-sm text-slate-600">
                  Run operations, inspect responses, and chat with conversational or tool agents.
                </p>
              </div>
              <div className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                UX preview: jobs and approvals tabs are still under active implementation.
              </div>
            </div>
          </header>

          <nav className="panel flex flex-wrap gap-2">
            {modules.map((module) => (
              <button
                key={module}
                type="button"
                className={`pill-nav ${activeModule === module ? "pill-nav-active" : "pill-nav-idle"}`}
                onClick={() => setActiveModule(module)}
                aria-current={activeModule === module ? "page" : undefined}
              >
                {module}
              </button>
            ))}
          </nav>
          {mainContent}
        </main>

        <section className="panel xl:sticky xl:top-4 xl:h-[calc(100vh-2rem)] xl:overflow-hidden">
          <h2 className="panel-title mb-3">Operation History</h2>
          {operations.length === 0 ? (
            <FeedbackEmpty message="No operations yet." />
          ) : (
            <div className="space-y-3 xl:max-h-[calc(100vh-8rem)] xl:overflow-auto pr-1">
              {operations.map((operation) => (
                <article key={operation.id} className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="font-medium capitalize text-slate-900">{operation.name}</span>
                    <span
                      className={
                        operation.success
                          ? "rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700"
                          : "rounded-full bg-rose-100 px-2 py-0.5 text-rose-700"
                      }
                    >
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
