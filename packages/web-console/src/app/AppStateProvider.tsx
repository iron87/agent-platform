import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/api-client";
import { createOperationResult, appendOperationResult } from "../lib/operation-history";
import { deleteProfile, loadProfiles, saveProfiles, upsertProfile } from "../lib/profile-store";
import type { ApiErrorView, ConsoleProfile, HealthResponse, OperationResult, ProfileState } from "../lib/types";

type SaveProfileInput = Omit<ConsoleProfile, "createdAt" | "updatedAt">;

interface AppStateContextValue {
  profileState: ProfileState;
  activeProfile: ConsoleProfile | null;
  operations: OperationResult[];
  saveProfile: (profile: SaveProfileInput) => void;
  removeProfile: (profileId: string) => void;
  selectProfile: (profileId: string) => void;
  runHealthCheck: () => Promise<void>;
}

const AppStateContext = createContext<AppStateContextValue | undefined>(undefined);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [profileState, setProfileState] = useState<ProfileState>(() => loadProfiles());
  const [operations, setOperations] = useState<OperationResult[]>([]);

  const activeProfile = useMemo(
    () => profileState.profiles.find((profile) => profile.id === profileState.activeProfileId) ?? null,
    [profileState],
  );

  useEffect(() => {
    saveProfiles(profileState);
  }, [profileState]);

  const value = useMemo<AppStateContextValue>(
    () => ({
      profileState,
      activeProfile,
      operations,
      saveProfile(profile) {
        setProfileState((prev) => {
          const next = upsertProfile(prev, profile);
          return {
            ...next,
            activeProfileId: next.activeProfileId ?? profile.id,
          };
        });
      },
      removeProfile(profileId) {
        setProfileState((prev) => deleteProfile(prev, profileId));
      },
      selectProfile(profileId) {
        setProfileState((prev) => ({ ...prev, activeProfileId: profileId }));
      },
      async runHealthCheck() {
        if (!activeProfile) {
          const error: ApiErrorView = {
            code: "PROFILE_REQUIRED",
            message: "Select a profile before running health checks",
          };
          const result = createOperationResult({
            name: "health",
            success: false,
            error,
          });
          setOperations((prev) => appendOperationResult(prev, result));
          throw error;
        }

        try {
          const payload = await apiRequest<HealthResponse>({
            profile: activeProfile,
            path: "/health",
            method: "GET",
          });

          const result = createOperationResult({
            name: "health",
            success: true,
            payload,
          });
          setOperations((prev) => appendOperationResult(prev, result));
        } catch (error) {
          const normalized = error as ApiErrorView;
          const result = createOperationResult({
            name: "health",
            success: false,
            error: normalized,
          });
          setOperations((prev) => appendOperationResult(prev, result));
          throw normalized;
        }
      },
    }),
    [activeProfile, operations, profileState],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error("useAppState must be used inside AppStateProvider");
  }
  return context;
}
