# Branch Protection Rules

This document outlines the branch protection rules that should be configured in GitHub for the GenAssist repository. These rules help maintain code quality and ensure proper review processes.

## Overview

GenAssist uses the **GitFlow** branching strategy with the following branch types:
- `main` - Production-ready code
- `development` - Integration branch for features
- `feature/*` - Feature development branches
- `release/*` - Release preparation branches
- `hotfix/*` - Critical production fixes

## Branch Protection Configuration

### Main Branch Protection

**Location**: GitHub Settings → Branches → Add rule → Branch name pattern: `main`

#### Required Settings:

1. **Require a pull request before merging**
   - ✅ Enable
   - ✅ Require approvals: **2**
   - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ Require review from Code Owners (if CODEOWNERS file exists)

2. **Require status checks to pass before merging**
   - ⚠️ Enable (optional - can be bypassed by admins)
   - Select required status checks (if CI/CD is configured):
     - Frontend tests
     - Backend tests
     - Linting checks
   - ✅ Require branches to be up to date before merging

3. **Require conversation resolution before merging**
   - ✅ Enable

4. **Require signed commits**
   - ⚠️ Optional (recommended for production)

5. **Require linear history**
   - ⚠️ Optional (recommended for cleaner history)

6. **Require merge queue**
   - ⚠️ Optional (for high-traffic repositories)

7. **Restrict who can push to matching branches**
   - ✅ Enable
   - Only repository administrators should have direct push access

8. **Do not allow bypassing the above settings**
   - ⚠️ Set based on team needs (recommended: allow admins to bypass)

9. **Lock branch**
   - ❌ Disable (not needed for main branch)

10. **Do not allow force pushes**
    - ✅ Enable

11. **Do not allow deletions**
    - ✅ Enable

### development Branch Protection

**Location**: GitHub Settings → Branches → Add rule → Branch name pattern: `development`

#### Required Settings:

1. **Require a pull request before merging**
   - ✅ Enable
   - ✅ Require approvals: **1**
   - ✅ Dismiss stale pull request approvals when new commits are pushed

2. **Require status checks to pass before merging**
   - ⚠️ Enable (optional - can be bypassed by admins)
   - Select required status checks (if CI/CD is configured)
   - ✅ Require branches to be up to date before merging

3. **Require conversation resolution before merging**
   - ✅ Enable

4. **Do not allow force pushes**
   - ✅ Enable

5. **Do not allow deletions**
   - ✅ Enable

### Feature Branches

**Branch name pattern**: `feature/*`

- ❌ No branch protection rules required
- Feature branches are created from `development` and merged back via pull requests
- Protection is enforced through the target branch (`development`) rules

### Release Branches

**Branch name pattern**: `release/*`

- ⚠️ Optional: Apply similar rules to `development` branch
- Typically requires 1 approval before merging to `main`

### Hotfix Branches

**Branch name pattern**: `hotfix/*`

- ⚠️ Optional: Apply similar rules to `main` branch
- May require expedited review process (document in CONTRIBUTING.md)

## Configuration Steps

1. Navigate to your repository on GitHub
2. Go to **Settings** → **Branches**
3. Click **Add rule** or **Add branch protection rule**
4. Enter the branch name pattern (e.g., `main`, `development`)
5. Configure the settings as outlined above
6. Click **Create** or **Save changes**

## Notes

- Branch protection rules are enforced at the repository level
- Repository administrators can bypass most rules (unless explicitly disabled)
- Status checks require CI/CD workflows to be configured in `.github/workflows/`
- Code owner reviews require a `CODEOWNERS` file in `.github/` or repository root

## Related Documentation

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [CONTRIBUTING.md](../CONTRIBUTING.md) - For workflow details
- [GitFlow Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow)

