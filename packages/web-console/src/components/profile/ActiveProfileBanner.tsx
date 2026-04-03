import type { ConsoleProfile } from "../../lib/types";

interface ActiveProfileBannerProps {
  profile: ConsoleProfile | null;
}

export function ActiveProfileBanner({ profile }: ActiveProfileBannerProps) {
  if (!profile) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
        No active profile selected. Create or select a profile to enable API operations.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900">
      <div className="font-semibold">Active profile: {profile.name}</div>
      <div className="mt-1">Mode: {profile.mode === "proxy" ? "Proxy (production-safe)" : "Direct (local/dev)"}</div>
      <div className="mt-2 text-xs text-slate-700">
        Initial release uses network-scoped access controls and does not include per-user sign-in.
      </div>
    </div>
  );
}
