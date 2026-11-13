# Codex / AI coding instructions — Home Assistant DiapStash

## Project and source of truth

- This is the **DiapStash Home Assistant custom integration**, Python, with HACS metadata. The current development baseline is **v1.1.5**. Read `docs/CODEX_HANDOFF.md`, `docs/ARCHITECTURE.md` and the existing `README.md` before making substantial changes.
- `custom_components/diapstash/` is the Home Assistant integration. The separate dashboard-card project is **not** part of this repository.
- Do not invent API fields, scopes or endpoints. Check existing code and official documentation, and request real sanitized sample JSON if uncertain.
- Respect the repository license and preserve existing user-facing behavior unless explicitly tasked otherwise.

## Branch and release safety (very important)

- **Never commit, push, tag or merge directly to `main` on your own.** Work only on a user-approved `dev` or `dev/*` branch. Inspect `git status` and the current branch first.
- Work only in a valid Git checkout. If `.git` metadata is missing, stop and ask the user; do not initialize a repository or attach an existing remote without explicit user direction.
- Never create a GitHub release, Git tag, or publish through HACS without explicit user approval.
- Do not increase `manifest.json` / `const.py` / README versions until instructed; dev changes can remain based on `1.1.5`.
- Inspect changes (`git diff`) and run local checks before proposing a commit. Explain any untested areas.

## Non-negotiable behavior to protect

- Home Assistant config entry supports **multiple DiapStash accounts** with separate API credentials. Account identity is the JWT `sub` claim, when available; preserve existing entry and device migration behavior.
- OAuth2 PKCE, token refresh and reauth must continue to work. Reauth updates the **existing** config entry and must reject a different account.
- **Never reload the whole integration on token-only config entry data updates**. In `__init__.py`, `_async_update_options` compares options with `coordinator.last_options` and reloads only when options change. Previously, reloads on OAuth token refresh caused all sensors to briefly become unavailable.
- `DiapStashEntity.available` should retain last known good data on **temporary** API/network errors, while still indicating initial no-data correctly. Preserve appropriate auth failure handling.
- Current diaper main state remains the primary diaper. Also expose `current_items`, `boosters`, `boosters_count`, `boosters_label` without changing the main state; count multiple booster items correctly.
- History fields `tags` and `note` supply `change_tags` (**list[str]**), `change_tags_label`, `change_note`, `change_has_note`. Do not display raw history JSON or private notes in logs.
- Local wearing-duration updates must not cause additional DiapStash API calls. Do not silently change entity unique IDs or suggested object IDs.
- Respect API read-only limits. API queries use `Authorization: Bearer ...`, `DS-API-CLIENT-ID`, a project User-Agent and needed OAuth scopes `cloud-sync.history`, `cloud-sync.stock`, `cloud-sync.types`, `offline_access`.
- API pagination in the current implementation starts with `page=0` and uses `size=50`. Avoid HTML scraping and avoid a browser-like User-Agent.
- Maintain EN/DE/FR/ES translation parity for every changed UI/config flow string.
- Preserve Home Assistant and HACS brand asset paths; a HACS/update-card missing-icon issue was still reported despite assets being present: investigate rather than claim it is fixed.

## Implementation and checks

- Python files use type annotations and Home Assistant async conventions. Prefer small, focused edits and tests over broad refactors.
- Do not persist OAuth secrets, access/refresh tokens or real account data in fixtures, output, diagnostics or prompts.
- Run `python tools/check_project.py` and `python -m unittest discover -s tests -v` after changes. These are **offline smoke checks, not a substitute** for running Home Assistant, Hassfest and HACS validation.
- For API/config-flow/coordinator changes, propose focused automated HA tests and a test plan; do not claim these exist or pass unless actually run.
- Keep `README.md`, `CHANGELOG.md` and `docs/ARCHITECTURE.md` consistent with changes where appropriate.
- Before reporting completion: summarize changed files, rationale, test commands/results and remaining risks; mention branch, but never imply a push/release happened without evidence.
