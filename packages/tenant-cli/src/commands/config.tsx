import type {Command} from 'commander';
import {loadConfig, saveConfig, resolveProfile} from '../config.js';
import {print, printError} from '../output.js';

export function registerConfigCommands(program: Command): void {
  const configCmd = program.command('config').description('Manage CLI profiles');

  configCmd
    .command('set')
    .description('Set profile configuration values')
    .option('--profile <name>', 'Profile name', 'default')
    .option('--base-url <url>', 'API base URL')
    .option('--api-key <key>', 'API key')
    .option('--output-mode <mode>', 'Output mode: text|json')
    .option('--poll-interval <seconds>', 'Job poll interval in seconds')
    .option('--default-agent-id <id>', 'Default agent ID for this profile')
    .action((opts: {
      profile: string;
      baseUrl?: string;
      apiKey?: string;
      outputMode?: string;
      pollInterval?: string;
      defaultAgentId?: string;
    }) => {
      const config = loadConfig();
      const existing = resolveProfile(config, {profileName: opts.profile});

      const updated = {
        ...existing,
        name: opts.profile,
        ...(opts.baseUrl !== undefined ? {baseUrl: opts.baseUrl} : {}),
        ...(opts.apiKey !== undefined ? {apiKey: opts.apiKey} : {}),
        ...(opts.outputMode === 'json' || opts.outputMode === 'text'
          ? {outputMode: opts.outputMode as 'text' | 'json'}
          : {}),
        ...(opts.pollInterval !== undefined
          ? {pollIntervalSeconds: Number(opts.pollInterval)}
          : {}),
        ...(opts.defaultAgentId !== undefined
          ? {defaultAgentId: opts.defaultAgentId}
          : {}),
      };

      config.profiles[opts.profile] = updated;
      saveConfig(config);
      print(`Profile '${opts.profile}' saved.`, 'text');
    });

  configCmd
    .command('get')
    .description('Show resolved configuration for a profile')
    .option('--profile <name>', 'Profile name', 'default')
    .option('--json', 'Output as JSON')
    .action((opts: {profile: string; json?: boolean}) => {
      const config = loadConfig();
      const profile = resolveProfile(config, {profileName: opts.profile});
      const safe = {...profile, apiKey: profile.apiKey ? '***' : ''};
      print(safe, opts.json ? 'json' : 'text');
    });

  configCmd
    .command('list')
    .description('List all stored profiles')
    .option('--json', 'Output as JSON')
    .action((opts: {json?: boolean}) => {
      const config = loadConfig();
      const names = Object.keys(config.profiles);
      if (opts.json) {
        print(names, 'json');
      } else {
        if (names.length === 0) {
          print('No profiles stored. Use `2brain config set` to create one.', 'text');
        } else {
          print(names.join('\n'), 'text');
        }
      }
    });

  configCmd
    .command('delete')
    .description('Delete a stored profile')
    .argument('<name>', 'Profile name to delete')
    .action((name: string) => {
      const config = loadConfig();
      if (!(name in config.profiles)) {
        printError(`Profile '${name}' not found`);
        process.exit(1);
      }
      delete config.profiles[name];
      saveConfig(config);
      print(`Profile '${name}' deleted.`, 'text');
    });
}
