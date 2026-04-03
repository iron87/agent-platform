export type OutputMode = 'text' | 'json';

import {renderText} from './ui/presenters.js';

export function print(value: unknown, mode: OutputMode): void {
  const effectiveMode: OutputMode = mode === 'text' && !isTTY() ? 'json' : mode;

  if (effectiveMode === 'json') {
    process.stdout.write(JSON.stringify(value, null, 2) + '\n');
  } else {
    process.stdout.write(renderText(value) + '\n');
  }
}

export function printError(message: string): void {
  process.stderr.write(`Error: ${message}\n`);
}

export function isTTY(): boolean {
  return Boolean(process.stdout.isTTY);
}
