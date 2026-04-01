import {readFileSync, writeFileSync, mkdirSync, existsSync} from 'fs';
import {join} from 'path';
import {homedir} from 'os';

export interface ProfileConfig {
  name: string;
  baseUrl: string;
  apiKey: string;
  outputMode: 'text' | 'json';
  pollIntervalSeconds: number;
  defaultAgentId?: string;
}

export interface CliConfig {
  profiles: Record<string, ProfileConfig>;
}

export interface ResolveProfileOptions {
  profileName?: string;
  baseUrl?: string;
  apiKey?: string;
  outputMode?: 'text' | 'json';
}

const CONFIG_DIR = join(homedir(), '.config', '2brain');
const CONFIG_PATH = join(CONFIG_DIR, 'config.json');

const DEFAULT_PROFILE: ProfileConfig = {
  name: 'default',
  baseUrl: process.env['BRAIN_BASE_URL'] ?? 'http://localhost:8000/api/v1',
  apiKey: process.env['BRAIN_API_KEY'] ?? '',
  outputMode: 'text',
  pollIntervalSeconds: 2,
};

export function loadConfig(): CliConfig {
  if (!existsSync(CONFIG_PATH)) {
    return {profiles: {}};
  }
  try {
    const raw = readFileSync(CONFIG_PATH, 'utf-8');
    return JSON.parse(raw) as CliConfig;
  } catch {
    return {profiles: {}};
  }
}

export function saveConfig(config: CliConfig): void {
  mkdirSync(CONFIG_DIR, {recursive: true});
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2) + '\n', 'utf-8');
}

export function resolveProfile(
  config: CliConfig,
  opts: ResolveProfileOptions,
): ProfileConfig {
  const stored = opts.profileName ? config.profiles[opts.profileName] : undefined;
  const base = stored ?? DEFAULT_PROFILE;

  return {
    ...base,
    ...(opts.baseUrl !== undefined ? {baseUrl: opts.baseUrl} : {}),
    ...(opts.apiKey !== undefined ? {apiKey: opts.apiKey} : {}),
    ...(opts.outputMode !== undefined ? {outputMode: opts.outputMode} : {}),
  };
}
