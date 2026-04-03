# Profile Storage Contract

## Storage medium
- Browser `localStorage`
- Key namespace: `two-brain.web-console.profiles.v1`

## JSON schema (logical)
```json
{
  "activeProfileId": "string",
  "profiles": [
    {
      "id": "string",
      "name": "string",
      "baseUrl": "string",
      "apiKey": "string",
      "mode": "proxy|direct",
      "defaultAgentId": "string|null",
      "createdAt": "ISO-8601",
      "updatedAt": "ISO-8601"
    }
  ]
}
```

## Constraints
- `name` must be unique in list.
- `baseUrl` must be valid URL.
- `apiKey` cannot be empty when `mode=direct`.
- Unknown fields must be ignored during load to support forward compatibility.

## Security behavior
- API key field is masked in UI by default.
- Reveal action is explicit and reversible by user interaction.
- Contract does not claim encryption-at-rest in browser storage.

## Migration policy
- If storage payload is malformed, application should:
- preserve raw data under backup key `two-brain.web-console.profiles.v1.backup.<timestamp>`
- reset to empty profile state
- show user-visible recovery notice
