import type { ConsoleProfile } from "../../lib/types";

interface ActiveProfileBannerProps {
  profile: ConsoleProfile | null;
}

export function ActiveProfileBanner({ profile }: ActiveProfileBannerProps) {
  if (!profile) {
    return (
      <div className="panel border-amber-200 bg-amber-50/90 text-sm text-amber-800">
        No active profile selected. Create or select a profile to enable API operations.
      </div>
    );
  }

  return (
    <div className="panel border-teal-200 bg-teal-50/80 text-sm text-teal-900">
      <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">Active profile</div>
      <div className="mt-1 font-semibold">{profile.name}</div>
      <div className="mt-1">
        Mode: <span className="font-medium">{profile.mode === "proxy" ? "Proxy (production-safe)" : "Direct (local/dev)"}</span>
      </div>
      <div className="mt-2 text-xs text-teal-800/80">
        Initial release uses network-scoped access controls and does not include per-user sign-in.
      </div>
    </div>
  );
}
