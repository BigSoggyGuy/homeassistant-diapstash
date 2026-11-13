# Testing checklist

## Lightweight local checks (no network / no Home Assistant install)

```cmd
python tools\check_project.py
python -m unittest discover -s tests -v
```

Also available as VS Code Tasks. Tests validate JSON files, local metadata/version consistency, readable PNG files, Python syntax and the small isolated token decoder helper. They **do not** verify live OAuth, HA entity lifecycle, API data or HACS integration.

## In an isolated Home Assistant test instance

1. Copy `custom_components/diapstash` to `/config/custom_components/diapstash` on a **test** HA instance; restart HA.
2. Set up one account with a distinct DiapStash API client and required scopes. Verify sensors and their known attributes.
3. Add a second test account with separate API credentials; verify entity ownership/unique IDs and HA restart behavior.
4. Exercise token refresh/401/reauth; expect **no whole-integration reload for token-only updates**. Verify invalid credentials start reauth and it updates the same account.
5. Simulate transient API/network outage after a valid result; previous values must stay available without spurious `unavailable` events. Verify actual auth failures remain actionable.
6. Wear a diaper with two boosters; check primary state, `current_items`, `boosters`, `boosters_count`, `boosters_label`.
7. Add multiple tags and a note to a change; verify `change_tags` is always a list, text label and note fields update, and privacy expectations are met.
8. Verify duration increases locally on configured interval; measure API requests to ensure no extra calls due to local timer.
9. Verify stock, reusables-to-wash, dynamic entities, brand/type/location breakdown and low-stock logic.
10. Verify all Config Flow/Options Flow strings in English, German, French and Spanish.
11. Run repository Actions (HACS + Hassfest) on the dev branch or pull request. Do not claim success until CI is green.

## Sensitive data

Do not paste access tokens, client secrets, refresh tokens, real user notes or full authenticated requests in issue reports or tests. Sanitize sample payloads.

## UI brand / HACS

The logo not appearing in the HACS search and update card was still reported after adding both brand folders. Test separately where the icon is missing, whether image endpoints respond, whether assets are present in the installed integration, and whether HACS uses remote brand metadata. Do not assume that a cache refresh alone fixes it.
