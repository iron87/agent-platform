import { normalizeError } from "./error-normalizer";
import type { ConsoleProfile } from "./types";

interface RequestOptions extends RequestInit {
  profile: ConsoleProfile;
  path: string;
}

function getBaseUrl(profile: ConsoleProfile): string {
  if (profile.mode === "proxy") {
    return "/api";
  }
  return profile.baseUrl.replace(/\/$/, "");
}

function buildHeaders(profile: ConsoleProfile, headers?: HeadersInit): Headers {
  const merged = new Headers(headers);
  merged.set("Content-Type", "application/json");

  if (profile.mode === "direct") {
    merged.set("Authorization", `Bearer ${profile.apiKey}`);
  }

  return merged;
}

export async function apiRequest<T>(options: RequestOptions): Promise<T> {
  const { profile, path, ...rest } = options;
  const response = await fetch(`${getBaseUrl(profile)}${path}`, {
    ...rest,
    headers: buildHeaders(profile, options.headers),
  });

  if (!response.ok) {
    throw await normalizeError(response, `Request to ${path} failed`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}
