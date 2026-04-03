# Polling Behavior Contract

## Job polling defaults
- Poll interval: 2000 ms
- Timeout: 300000 ms (5 minutes)
- Jitter: optional +/- 200 ms for burst smoothing

## Terminal states
- `completed`
- `failed`
- `cancelled`

## State machine
- Initial after submit: `queued`
- Transitional: `running`
- Terminal: one of terminal states

## UI requirements
- Display elapsed time while polling.
- Provide manual stop action to end polling early.
- On timeout, show explicit timeout message and last known job status.

## Retry behavior
- Automatic retry for transient network failure: up to 3 attempts with linear backoff (2s, 4s, 6s).
- No automatic retry on 4xx responses.

## Telemetry hooks
- Emit client-side event on:
- polling started
- polling terminal state reached
- polling timeout reached
- polling aborted by user
