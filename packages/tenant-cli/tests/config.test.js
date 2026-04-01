import { describe, expect, it } from 'vitest';
import { resolveProfile } from '../src/config';
describe('resolveProfile', () => {
    it('prefers explicit flags over stored defaults', () => {
        const profile = resolveProfile({
            profiles: {
                local: {
                    name: 'local',
                    baseUrl: 'http://localhost:8000/api/v1',
                    apiKey: 'stored-key',
                    outputMode: 'text',
                    pollIntervalSeconds: 2,
                },
            },
        }, {
            profileName: 'local',
            baseUrl: 'http://override.example/api/v1',
            apiKey: 'flag-key',
            outputMode: 'json',
        });
        expect(profile.baseUrl).toBe('http://override.example/api/v1');
        expect(profile.apiKey).toBe('flag-key');
        expect(profile.outputMode).toBe('json');
    });
});
