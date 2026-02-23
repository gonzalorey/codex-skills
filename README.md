# codex-skills

Shared repository of reusable Codex skills.

## Repository layout

```text
codex-skills/
  skills/
    <skill-name>/
      SKILL.md                 # required
      agents/openai.yaml       # recommended
      scripts/                 # optional
      references/              # optional
      assets/                  # optional
      tests/                   # optional but recommended for scripts
```

## Add a new skill

1. Choose a folder name in lowercase hyphen-case (example: `invoice-reconciliation`).
2. Create `skills/<skill-name>/SKILL.md` with YAML frontmatter:

   ```yaml
   ---
   name: <skill-name>
   description: Clear trigger description of what the skill does and when to use it.
   ---
   ```

3. Write concise, imperative instructions in `SKILL.md`:
   - Required execution flow.
   - Main commands.
   - Safety/approval gates.
   - Required and optional environment variables.
4. Add reusable resources only when needed:
   - `scripts/` for deterministic, repeatable operations.
   - `references/` for docs/schema/policies loaded on demand.
   - `assets/` for templates and output resources.
5. Add `agents/openai.yaml` so the skill appears cleanly in skill lists and chips.
6. If scripts are added, include tests under `tests/` and run them before committing.
7. Commit the skill with a small example of real usage in the PR description.

## Skill quality checklist

- `SKILL.md` exists and frontmatter has only `name` + `description`.
- Description includes strong trigger context ("use when...").
- Commands in `SKILL.md` are executable as written.
- External actions are gated (dry-run, explicit approval, no implicit send/post).
- Scripts fail safely and explain next steps on missing credentials/dependencies.
- References are linked from `SKILL.md` (no orphan docs).

## Agent-focused guidelines

Codex agents working in this repo should follow this order:

1. Read `AGENTS.md` at repo root.
2. Read target skill `SKILL.md`.
3. Load only the specific `references/` files needed for the request.
4. Reuse or patch existing `scripts/` instead of rewriting equivalent logic.
5. Keep edits minimal and preserve existing safety gates.
6. Validate changed scripts/tests before finishing.

## Existing skills

- `skills/facturacion-monotributo-amigos`
- `skills/recibos-empleadas-domesticas`

## PR template

Use the repository PR template at `.github/pull_request_template.md` for skill additions and updates.
For non-skill work, choose `.github/PULL_REQUEST_TEMPLATE/maintenance.md` in GitHub's template picker.
