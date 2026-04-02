import {Command} from 'commander';

import {registerAgentsCommands} from './commands/agents.js';
import {registerApprovalsCommands} from './commands/approvals.js';
import {registerConfigCommands} from './commands/config.js';
import {registerChatCommands, registerRunCommands} from './commands/run.js';
import {registerJobsCommands} from './commands/jobs.js';

export async function runCli(argv: string[] = process.argv): Promise<void> {
  const program = new Command();

  program
    .name('2brain')
    .description('Ink-based tenant CLI for the 2brain public API')
    .showHelpAfterError(true)
    .allowExcessArguments(false);

  registerConfigCommands(program);
  registerRunCommands(program);
  registerChatCommands(program);
  registerJobsCommands(program);
  registerAgentsCommands(program);
  registerApprovalsCommands(program);

  await program.parseAsync(argv);
}
