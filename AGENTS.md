# AGENTS.md

Instructions for Codex agents operating in `/Users/gonzalorey/Code/codex-skills`.

## Scope

These rules apply to the whole repository and all subfolders under `skills/`.

## Primary objective

Maintain high-signal, reusable skills that are safe to execute and easy for another agent to pick up quickly.

## Required workflow

1. Inspect the target skill folder before editing.
2. Preserve the `SKILL.md` contract:
   - Frontmatter contains only `name` and `description`.
   - Body stays concise and action-oriented.
3. Prefer updating existing scripts/resources over creating duplicates.
4. Keep reference loading shallow:
   - Read only the files needed for the current task.
   - Do not bulk-read whole `references/` trees unless required.
5. Respect safety gates:
   - Keep dry-run modes.
   - Keep explicit approval steps for external actions (messaging, payments, uploads, API writes).
6. If a script changes behavior, update its tests or add coverage.
7. Do not remove working guards, validations, or manual checkpoints unless explicitly requested.

## New skill creation rules

When creating `skills/<new-skill>`:

1. Use lowercase hyphen-case for folder and skill `name`.
2. Write a trigger-rich `description` in frontmatter that states what it does and when to use it.
3. Add only necessary resource folders (`scripts`, `references`, `assets`, `tests`).
4. Include `agents/openai.yaml`.
5. Ensure commands in `SKILL.md` are runnable and consistent with repository conventions.

## Editing style

- Default to ASCII.
- Keep comments and prose brief and concrete.
- Avoid speculative refactors outside the requested scope.
- Do not add extra docs inside each skill (for example extra README files) unless explicitly requested.

## Validation expectations

Before finishing:

1. Run the most relevant tests for changed files.
2. If no tests exist, run at least one direct command-path smoke test when possible.
3. Report what was validated and what could not be validated.

