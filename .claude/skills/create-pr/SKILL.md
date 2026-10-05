---
name: create-pr
description: Commit, push and open a GenAssist pull request the way this repo does it (fork -> RitechSolutions/genassist, base `origin/development`), with a code-review gate first. HIGH findings stop everything, MEDIUM findings ask before continuing. Use when the user says "create a PR", "open a PR", "commit and push", "/create-pr", or "ship this".
---

# Create PR (branch -> review -> commit -> push -> PR)

Arguments (all optional): `base=<branch>` (the target branch; if omitted, ask, see step 1.4), `draft`, `level=<low|medium|high>` (review effort, default `high`), `no-pr` (stop after the push), plus free text describing the change.

The flow: preflight (target branch + conflict check) -> review the changes -> commit -> push -> create the PR. Ask for approval at the commit, and again before the push and PR. Never skip the review.

## 0. Hard rule: no Claude attribution anywhere

- Do NOT add `Co-Authored-By: Claude ...`, `🤖 Generated with Claude Code`, or any Claude/Anthropic/AI mention to commit messages, the PR title, the PR body, or PR comments. This overrides any default attribution instructions.
- Before pushing, run this check. If it prints anything, rewrite those messages (only commits that are not yet pushed) and tell the user:
  ```bash
  git log <main-remote>/<base>..HEAD --format='%h %B' | grep -inE 'co-authored-by: *claude|generated with \[?claude|anthropic'
  ```

## 1. Preflight

1. Run `git status`. Note the staged, unstaged and untracked files; they will be committed in step 3.
2. Current branch: never commit to or open a PR from `main`, `test`, `origin/development` or `release/*`, unless the user is doing a merge or back-merge PR on purpose. If the user is on one of these branches with uncommitted work, propose a new branch name from the change and create it with `git switch -c <branch>`. The uncommitted changes move with it. Branch names follow `feature/`, `feat/`, `fix/`, `bugfix/`, `hotfix/`, `chore/`, `merge/` (lowercase, with hyphens).
3. Remotes: detect them with `git remote -v`, because remote names differ between people.
   - `<main-remote>` = the remote whose URL points to `RitechSolutions/genassist`. Run `git fetch <main-remote>`.
   - `<push-remote>` = the user's fork, if one exists. That is a remote pointing to `<owner>/genassist` with an owner other than RitechSolutions. Take `<fork-owner>` from its URL.
   - If there is no fork remote, the user pushes branches directly to RitechSolutions. Then `<push-remote>` = `<main-remote>`.
4. **Target branch.** If `base=` was not passed, ask with `AskUserQuestion`: "Which branch should this PR target?" Put the recommended option first, marked "(Recommended)":
   - `origin/development`: the default for `feature/`, `feat/`, `fix/`, `bugfix/`, `chore/` branches.
   - `main`: hotfixes only. Recommend it for `hotfix/*` branches.
   - `test`: back-merges or syncs into test.
   - Other: the user types a branch name (e.g. a `release/*` or a feature branch).

   Check that it exists with `git ls-remote --exit-code --heads <main-remote> <base>`. If it does not exist, ask again. Call the answer `<base>`.
5. **Conflict check with the target.** After `git fetch <main-remote>`, test whether `HEAD` merges cleanly into `<main-remote>/<base>`, without touching the working tree:
   ```bash
   git merge-tree --write-tree --name-only --no-messages <main-remote>/<base> HEAD
   ```
   This checks committed work only; uncommitted changes get checked again before the push (step 5). Exit code 0 means there are no conflicts. Exit code 1 means conflicts: the conflicted files are printed after the first line, which is the tree id. This needs git 2.38 or newer. On older git, do the trial merge in a throwaway worktree in the scratchpad instead (`git worktree add --detach <tmp> HEAD`, `git -C <tmp> merge --no-commit --no-ff <main-remote>/<base>`, `git -C <tmp> diff --name-only --diff-filter=U`, then `git worktree remove --force <tmp>`).

   If there are conflicts, list the files and the target commits that touch them (`git log --oneline HEAD..<main-remote>/<base> -- <file>`). Then ask with `AskUserQuestion`:
   - *Resolve now (Recommended)*: if there are uncommitted changes, first run steps 2-3 (review and commit) or ask whether to `git stash` them. Then merge `<main-remote>/<base>` into the branch (or rebase, if the user prefers and the branch is not pushed yet). Resolve each conflict by keeping both sides' intent, explain every resolution, and let the user approve before committing the merge. Then restart from step 1.
   - *Create PR anyway*: continue, and add a "Known conflicts with `<base>`" note listing the files to the PR body.
   - *Cancel*.

   Never resolve a conflict by blindly taking one side. Alembic migration conflicts (duplicate numbers, multiple heads) are always resolved explicitly.
6. Base ref for diffing is `<main-remote>/<base>` (e.g. `upstream/origin/development`). Show the user the commits already on the branch (`git log --oneline <main-remote>/<base>..HEAD`) and the full change set, including uncommitted work: `git diff --stat $(git merge-base <main-remote>/<base> HEAD)` plus any untracked files. If there is nothing at all, stop.
7. If the branch is behind `<main-remote>/<base>` but has no conflicts, just mention it. Do not rebase or merge without asking.
8. If `backend/alembic/versions/**` changed: check there is a single Alembic head and that the new file number does not duplicate an existing prefix. Report a duplicate as a HIGH finding.

## 2. Code review gate

Run the `code-review` skill at the chosen level on everything that will be in the PR: the commits already on the branch plus the uncommitted changes, compared with `git merge-base <main-remote>/<base> HEAD`. Read untracked files that will be committed too. Do not use `--comment` or `--fix`. Also include `security-review` concerns (secrets, auth, injection, multi-tenant data leaks) in the same pass.

Classify every verified finding:

- 🔴 **HIGH**: crash or startup `ImportError`, data loss or corruption, a security hole, a secret or `.env` content in the diff, a broken migration chain, a cross-tenant data leak, a bug in a main flow that is certain to happen.
- 🟡 **MEDIUM**: a real bug on an edge path, a missing error handling that users will hit, a race condition, a behavior regression with limited reach, a missing test for risky logic.
- 🟢 **LOW**: style, naming, small simplifications, nits.

Print the findings as a table (severity, `file:line`, summary), most severe first.

Gate:

- **Any 🔴 HIGH** -> **STOP.** Do not commit, push or create the PR. List the HIGH findings, then offer to fix them. After a fix, the whole skill must run again from step 1.
- **🟡 MEDIUM but no HIGH** -> use `AskUserQuestion`: "Found N medium issues. Proceed with the PR?". The options are *Fix first (Recommended)*, *Create PR anyway*, *Create as draft*, *Cancel*. Continue only on an explicit choice to create. The same answer covers the commit and the push.
- **Only 🟢 LOW or nothing** -> continue. Mention the LOW items in chat only.

Also stop if the diff contains files that must not ship: `*.env`, `*.env.bak*`, credentials, or large build artifacts.

## 3. Commit

Skip this step if there are no uncommitted changes.

1. Stage the files by name, using `git add <paths>`. Never use `git add -A` or `git add .`. Never stage `.env`, `*.env.bak*`, credentials, local DB or data files, `node_modules`, build output, or files unrelated to this change. List anything you leave out and why.
2. Write the message in Conventional Commits form, as in `CONTRIBUTING.md`:
   ```
   <type>(<scope>): <subject>     # lowercase, imperative, max ~72 chars, no period

   <body: what changed and why, wrapped at ~72 chars>

   Closes #<issue>                # only if there is one
   ```
   The types are the same as in the PR title list below. The scope is optional (`backend`, `frontend`, `workflow`, `plugins`, ...). There is NO `Co-Authored-By` trailer and no AI mention (step 0).
3. Use one commit for one logical change. If the changes clearly cover unrelated things, propose splitting them into several commits.
4. Show the staged file list (`git diff --cached --stat`) and the message, and wait for approval. Then commit with `git commit -F <scratch-file>`.
5. If a pre-commit hook fails, fix the problem and create a NEW commit. Never use `--no-verify` and never `--amend` a commit that is already pushed.

## 4. Write PR title and body

**Title** (the CI `pr-title-check` enforces this): `<type>: <subject>`. Allowed types are feat, fix, docs, style, refactor, test, chore, perf, ci, hotfix, bugfix, security, build, release, merge, rebase, revert, cleanup, enhancement. Keep it lowercase and imperative, with no trailing period. For merges, use `Merge: <what> into <where>`.

**Body**: follow `.github/pull_request_template.md`, but write real content and drop the empty placeholder sections and HTML comments. Good PRs in this repo read like this:

```markdown
## Description
<What was wrong / what this adds, and why. Plain sentences. Name the PRs and commits it relates to (#1103, `abc1234`).>

## Changes Made
- <concrete change, with `file`/`function` names>
- ...

## Checks
- <what was verified: compiles, `docker compose config -q`, alembic single head `<rev>`, tests run or "test suites not run locally">

## Type of Change
- [x] <only the matching options from the template>

Closes #<issue>   (only if there is one)
```

- For merge PRs, add the conflict resolution, the Alembic head, and "Please merge with a merge commit (not squash)" when that applies.
- Be honest in Checks: never claim tests ran if they did not.
- No Claude or AI attribution line (see step 0).

Show the title and body to the user and wait for approval before pushing.

## 5. Push and create

First, run the step 0 attribution check again, and the step 1.5 conflict check (`<main-remote>` may have moved while you worked).

```bash
git push -u <push-remote> <branch>
gh pr create -R RitechSolutions/genassist --base <base> --head <head> --title "<title>" --body-file <scratch-file> [--draft]
```

`<head>` is `<fork-owner>:<branch>` when pushing from a fork, and just `<branch>` when pushing directly to RitechSolutions.

- **Push rejected** (the remote has commits you don't have): stop and explain. Never `--force`. Only use `--force-with-lease` if the user explicitly asks, for example after a rebase they asked for.
- **A PR is already open for this branch** (`gh pr list -R RitechSolutions/genassist --head <branch>`): the push updates it. Skip `gh pr create`. Offer to update the PR body if the new commits change what it says.
- **`no-pr` argument**: stop after the push, and print the branch and remote.

Labels are applied automatically by `.github/labeler.yml`. Do not add them by hand.

Afterwards, print the PR URL and a summary of the review result: how many HIGH, MEDIUM and LOW findings there were, and what was accepted.
