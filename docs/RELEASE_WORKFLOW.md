# Dev → review → release workflow

**Do not push to `main` while developing.** Codex must not make network-changing Git actions without explicit user approval.

## Before any change

```cmd
git status
git branch --show-current
git remote -v
```

Switch only to the user-approved `dev` / `dev/*` branch. Do not run `git switch -c dev` blindly if a branch already exists; check `git branch -a` and select the right base.

## While developing

- Keep changes small and explain the diff.
- Add tests for bug fixes and API mapping updates.
- Run `python tools\check_project.py` and `python -m unittest discover -s tests -v`.
- Test in a separate HA instance and run HACS/Hassfest workflow; report any limits.
- Do not change versions/tags in unrelated edits.

## When user explicitly approves a release

- Decide version and update **together**: `custom_components/diapstash/manifest.json`, `custom_components/diapstash/const.py` (`INTEGRATION_VERSION` affects User-Agent), `README.md`, `CHANGELOG.md` and release notes.
- Confirm `strings.json` / translations match.
- Confirm brand files are included and the UI issue has actually been checked if relevant.
- Review CI on the specific release candidate commit.
- Merge dev changes to `main` only after explicit approval.
- Tag and publish only after explicit approval. If intermediate dev versions never shipped, release notes should summarize all user-facing changes since the last **actually published** version.
- Do not assume GitHub published version from a ZIP version number.
