---
name: create-pr
description: Commit, push and open a GenAssist pull request the way this repo does it, linked to its required Azure DevOps ticket (fork -> RitechSolutions/genassist, base `origin/development`), with a code-review gate first. HIGH findings stop everything, MEDIUM findings ask before continuing. Use when the user says "create a PR", "open a PR", "commit and push", "/create-pr", or "ship this".
---

# Create PR (branch -> review -> commit -> push -> PR)

Arguments (all optional): `ticket=<id>[,<id>...]` (Azure DevOps work item; if omitted, ask, see step 0b), `base=<branch>` (the target branch; if omitted, ask, see step 1.4), `draft`, `level=<low|medium|high>` (review effort, default `high`), `no-pr` (stop after the push), plus free text describing the change.

The flow: Azure ticket -> preflight (branch name, target branch, conflict check) -> review the changes -> commit -> push -> create the PR. Ask for approval at the commit, and again before the push and PR. Never skip the review.

## 0. Hard rule: no Claude attribution anywhere

- Do NOT add `Co-Authored-By: Claude ...`, `🤖 Generated with Claude Code`, or any Claude/Anthropic/AI mention to commit messages, the PR title, the PR body, or PR comments. This overrides any default attribution instructions.
- Before pushing, run this check. If it prints anything, rewrite those messages (only commits that are not yet pushed) and tell the user:
  ```bash
  git log <main-remote>/<base>..HEAD --format='%h %B' | grep -inE 'co-authored-by: *claude|generated with \[?claude|anthropic'
  ```

## 0b. Hard rule: an Azure DevOps ticket is required

Every PR must reference at least one Azure DevOps work item (`https://dev.azure.com/Ritech/GenAssist/_workitems/edit/<id>`). Get it before anything else.

1. **Ask for it.** If `ticket=` was not passed, ask with `AskUserQuestion`: "Which Azure DevOps ticket is this for?" If a number is visible in the current branch name or the commit subjects (e.g. `fix/67572-...`, `(66739, 66740)`), offer it first as "(Recommended)". Otherwise the user types it through "Other". Never invent a number or pick one without the user confirming it.
2. **Validate.** Each id is 4-7 digits, with no `#` and no `AB#` prefix (strip those if typed). Several ids are allowed, comma-separated. If the answer is not a valid id, say so and ask again.
3. **No ticket = no PR.** If the user has no ticket, STOP: no commit, no push, no PR. Ask them to create the work item in Azure DevOps first. The only exception is merge, back-merge, sync and release PRs (a `merge/`, `sync/` or `release/` branch, or `main` -> `test` -> `development` back-merges). For those, offer *No ticket (merge/release PR)* as an option.

Call the result `<ticket>` (the first id) and `<tickets>` (all of them). It is used in:

| Where | Format | Example |
|---|---|---|
| Branch name | `<prefix>/<ticket>-<slug>` | `fix/67572-display-workflow-test-errors` |
| Commit footer | `AB#<id>`, one per ticket | `AB#67572` |
| PR title | `<type>: <subject> (<tickets>)` | `fix: display workflow test errors (67572)` |
| PR body | `## Related Issues` with `AB#<id>` and the work item link | see step 4 |

`AB#<id>` is what Azure Boards uses to link GitHub commits and PRs back to the work item.

## 1. Preflight

1. Run `git status`. Note the staged, unstaged and untracked files; they will be committed in step 3. Get the Azure ticket (step 0b) before going on.
2. **Branch name.** Never commit to or open a PR from `main`, `test`, `origin/development` or `release/*`, unless the user is doing a merge or back-merge PR on purpose. Always ask for the branch name with `AskUserQuestion`, even when one could be inferred:
   - **Change type first.** When a new branch will be created, first ask with `AskUserQuestion`: "What kind of change is this?" Recommend the option that fits the diff, marked "(Recommended)":
     - *Feature*: new functionality.
     - *Fix*: a bug fix going to `origin/development`.
     - *Hotfix*: an urgent production fix going to `main`.
     - *Other*: the user types `chore`, `docs`, `refactor`, `perf`, `test` or `security`.

     The answer sets `<change-type>`, which is used everywhere after this:

     | Change type | Branch prefix | Commit / PR title type | Template "Type of Change" | Recommended target (step 1.4) |
     |---|---|---|---|---|
     | Feature | `feature/` | `feat` | ✨ New feature | `origin/development` |
     | Fix | `fix/` | `fix` | 🐛 Bug fix | `origin/development` |
     | Hotfix | `hotfix/` | `hotfix` | 🐛 Bug fix | `main` |
     | chore / docs / refactor / perf / test / security | `chore/`, `docs/`, `refactor/` ... (same word) | same word | 🔧 Config / 📚 Docs / 🏗️ Core / 🧪 Test | `origin/development` |

     If the user is already on a non-protected branch, take `<change-type>` from its prefix, and ask only if the prefix doesn't match the diff (e.g. a `fix/` branch that clearly adds a new feature).
   - **On a protected branch:** ask "Which branch name should I create for this change?" Offer 2-3 names as `<prefix>/<ticket>-<slug>`, using the prefix from `<change-type>` (e.g. `fix/67572-display-workflow-test-errors`, `feature/67574-loop-node`), with the best one first, marked "(Recommended)". The user can also type their own name through "Other". Create it with `git switch -c <branch>`; uncommitted changes move with it.
   - **Already on a non-protected branch:** ask "Use the current branch `<branch>`?" The options are *Keep `<branch>` (Recommended)*, *Rename it*, and *New branch from here*. Only offer *Rename it* if the branch has not been pushed and has no open PR. Rename with `git branch -m <new>`. If the current name does not contain `<ticket>`, recommend *Rename it* (or *New branch from here* if it is already pushed) instead of *Keep*. A pushed branch without the ticket may be kept, but then the ticket must be in the title and body.

   Check every name before using it (detect the remotes from item 3 first):
   - Its prefix matches `<change-type>` (or `merge/`, `sync/` or `release/` for those PRs). If the user types `feat/` or `bugfix/`, accept it and note that the team uses `feature/` and `fix/`. The rest of the name is lowercase, with hyphens, no spaces, and under ~60 characters.
   - New branches must have the form `<prefix>/<ticket>-<slug>`, e.g. `fix/67570-csv-export`. Ticket-exempt merge and release PRs (step 0b.3) are the only exception.
   - It is not already used, either locally (`git rev-parse --verify --quiet refs/heads/<name>`) or on the main or push remote (`git ls-remote --exit-code --heads <remote> refs/heads/<name>`).

   If the name is invalid or taken, say why and ask again.
3. Remotes: detect them with `git remote -v`, because remote names differ between people.
   - `<main-remote>` = the remote whose URL points to `RitechSolutions/genassist`. Run `git fetch <main-remote>`.
   - `<push-remote>` = the user's fork, if one exists. That is a remote pointing to `<owner>/genassist` with an owner other than RitechSolutions. Take `<fork-owner>` from its URL.
   - If there is no fork remote, the user pushes branches directly to RitechSolutions. Then `<push-remote>` = `<main-remote>`.
4. **Target branch.** If `base=` was not passed, ask with `AskUserQuestion`: "Which branch should this PR target?" Put the recommended option first, marked "(Recommended)", based on `<change-type>` (see the table in item 2):
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

Run the `code-review` skill at the chosen level on everything that will be in the PR: the commits already on the branch plus the uncommitted changes. Always pass the scope explicitly in its args. Without it, `code-review` falls back to `@{upstream}...HEAD` or `main...HEAD`, which is the wrong base here.

1. Compute it: `MB=$(git merge-base <main-remote>/<base> HEAD)`. The scope is `git diff $MB` (commits plus working tree) plus the untracked files that will be committed.
2. Invoke the skill with args like this: `<level> review exactly: git diff <MB-sha> (merge-base with <main-remote>/<base>; includes uncommitted changes) + untracked: <paths>`.
3. Before using the results, check that the files reviewed match `git diff --name-only $MB` plus the untracked files. If they don't match, run the review again.

Do not use `--comment` or `--fix`. Also include `security-review` concerns (secrets, auth, injection, multi-tenant data leaks) in the same pass.

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

   AB#<ticket>                    # one line per ticket; required (step 0b)
   ```
   Use the type that matches `<change-type>` (`feat`, `fix`, `hotfix`, `chore`, ...). The types are the same as in the PR title list below. The scope is optional (`backend`, `frontend`, `workflow`, `plugins`, ...). There is NO `Co-Authored-By` trailer and no AI mention (step 0).
3. Use one commit for one logical change. If the changes clearly cover unrelated things, propose splitting them into several commits.
4. Show the staged file list (`git diff --cached --stat`) and the message, and wait for approval. Then commit with `git commit -F <scratch-file>`.
5. If a pre-commit hook fails, fix the problem and create a NEW commit. Never use `--no-verify` and never `--amend` a commit that is already pushed.

## 4. Write PR title and body

**Title** (the CI `pr-title-check` enforces this): `<type>: <subject> (<tickets>)`, where `<type>` comes from `<change-type>`, e.g. `fix: preserve ML prediction output types (66739, 66740)`. The ticket suffix is required (step 0b). Allowed types are feat, fix, docs, style, refactor, test, chore, perf, ci, hotfix, bugfix, security, build, release, merge, rebase, revert, cleanup, enhancement. Keep it lowercase and imperative, with no trailing period. For merges, use `Merge: <what> into <where>`.

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
- [x] <the option for `<change-type>`, plus any others that also apply>

## Related Issues
- AB#<ticket> - https://dev.azure.com/Ritech/GenAssist/_workitems/edit/<ticket>   (one line per ticket; required)
- Closes #<github-issue>   (only if there is one)
```

- For merge PRs, add the conflict resolution, the Alembic head, and "Please merge with a merge commit (not squash)" when that applies.
- Be honest in Checks: never claim tests ran if they did not.
- No Claude or AI attribution line (see step 0).

Show the title and body to the user and wait for approval before pushing.

## 5. Push and create

First, confirm that the PR title and body contain every `<tickets>` id (step 0b). Then run the step 0 attribution check again, and the step 1.5 conflict check (`<main-remote>` may have moved while you worked).

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
