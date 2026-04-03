import { z } from "zod";
import type { ConsoleProfile } from "../../lib/types";

export const profileSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1).max(64),
  baseUrl: z.string().url().refine((value) => value.startsWith("http://") || value.startsWith("https://"), {
    message: "Base URL must start with http:// or https://",
  }),
  apiKey: z.string(),
  mode: z.enum(["proxy", "direct"]),
  defaultAgentId: z.string().optional(),
});

export type ProfileFormValue = z.infer<typeof profileSchema>;

export function validateProfile(value: ProfileFormValue): { ok: true } | { ok: false; message: string } {
  const parsed = profileSchema.safeParse(value);
  if (!parsed.success) {
    return { ok: false, message: parsed.error.issues[0]?.message ?? "Invalid profile" };
  }

  if (parsed.data.mode === "direct" && !parsed.data.apiKey.trim()) {
    return { ok: false, message: "API key is required in direct mode" };
  }

  return { ok: true };
}

export function createProfileFromForm(value: ProfileFormValue): Omit<ConsoleProfile, "createdAt" | "updatedAt"> {
  return {
    id: value.id,
    name: value.name.trim(),
    baseUrl: value.baseUrl.trim(),
    apiKey: value.apiKey,
    mode: value.mode,
    defaultAgentId: value.defaultAgentId?.trim() || undefined,
  };
}
