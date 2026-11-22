# CLAUDE.md

Guidance for coding agents working in this repository.
Sections 1–4 adapt the Karpathy-inspired guidelines from
[multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills);
the rest is specific to this project.

**Tradeoff:** these rules favour caution over speed. For trivial changes, use judgment.

## 1. Think before coding

- State assumptions explicitly. If a request has more than one reading, say so and ask; don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- Never invent Home Assistant or Marketplace APIs (methods, selectors, translation keys, MDI icons). If unsure an API exists in the target version, check the installed `homeassistant` package first.
- Before changing what a total or a budget means, ask what counts. Get two real cases (e.g. Netflix, Spotify Family) before designing.

## 2. Simplicity first

- Minimum code that solves the request. No speculative features, options or abstractions.
- No error handling for impossible cases; real failure modes are handled and tested.
- If it could be half the length, rewrite it.

## 3. Surgical changes

- Touch only what the request needs. Don't reformat or "improve" adjacent code; match the existing style.
- Remove only what your own change made unused. Mention unrelated dead code, don't delete it.
- Every changed line should trace back to the request.

## 4. Goal-driven execution

- Turn the task into checks: "fix X" → a test that reproduces X, then make it pass.
- Write the test first, run it and watch it fail, then implement. Check every new test also fails against the old code; for timer logic, break the code on purpose once and confirm a test catches it.
- Report what was verified (tests run, CI, real HA) separately from what was only read. Never say "works" for something not run.

## Project

Home Assistant custom integration `subscription_tracker`: streaming subscriptions with renewals, monthly and annual totals, budget, 30-day timeline and monthly history. Distributed through the Home Assistant Marketplace (ex HACS, same `hacs.json`). The Lovelace card ships with the integration (`custom_components/subscription_tracker/www/`, since 0.5.0, as required by the HACS review): `frontend.py` serves it at `/subscription_tracker/subscription-tracker-card.js` and keeps one dashboard resource with `?v=<version>` (YAML resources: extra frontend module). The old card repo is archived. `CARD_VERSION` in the JS equals the manifest version (tested).

### Architecture

- `calc.py` is pure (no `homeassistant` imports, basic types in and out): renewals, totals, budget, timeline, currencies. Calculations go here, with tests in `tests/test_calc.py`.
- `sensor.py` (one sensor per subscription plus the summary), `config_flow.py` (subscriptions, options, budget), `__init__.py` (setup, migrations, `add_price_history` service, monthly history), `const.py`.
- Data that grows over time (monthly history) lives in a `Store` (`subscription_tracker.monthly_history`), not in `entry.options`: the options flow would rewrite it and every update reloads the entry.
- The integration computes, the card only presents. Every value a card shows is an attribute documented in `docs/attributes-contract.md`. Bump `contract_version` only for breaking changes (rename, removal, change of meaning); new attributes or enum values are additive.
- Billing cycles: one table in `const.py` (`BILLING_CYCLE_MONTHS`) used by calculations, config flow and tests.

### Rules

- `manifest.json`: `domain` and `name` first, the other keys sorted; no external requirements. Version consistent across manifest, card and git tag.
- Translations: `strings.json` == `translations/it.json`; `translations/en.json` has the same keys. UI text is Italian; code, comments, docstrings, README and docs are English.
- The payment method is never exposed in attributes (it stays in `entry.data`, so in backups). `notes` is exposed: no personal data there.
- Options flows return the complete options (HA replaces `entry.options`, it does not merge); test that existing data (price history, pause) survives an edit.
- Use `dt_util.now().date()` / the HA time zone, never `date.today()`.
- A duplicate config entry `unique_id` is only logged by HA: check for collisions before `async_update_entry(unique_id=...)`.
- Release checklist: hassfest, HACS validation and pytest green in CI; translations aligned; versions consistent; README updated (the Marketplace shows the README of the installed tag); GitHub release; test on a real HA before tagging.

### Tests

- Python 3.14 with `pytest-homeassistant-custom-component` (`pip install -r requirements_test.txt`), then `pytest` from the repo root.
- Time via `freezer` and `async_fire_time_changed`; entities that poll update on any time move, so timer tests must assert on entities without polling.
- CI: `.github/workflows/` (hassfest, HACS, tests). Workflow files are edited by the maintainer.

### Commits

Conventional title only, in English (`feat:`, `fix:`, `test:`, `docs:`, `chore:`): no body, no trailers. The maintainer commits and pushes.
