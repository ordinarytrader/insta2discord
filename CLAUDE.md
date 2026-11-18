# CLAUDE.md

Context for Claude Code sessions in this repo.

## Branch clean-up

Don't let old branches pile up on GitHub.

- After merging a `claude/...` branch into the default branch, delete it on GitHub: `git push origin --delete <branch>`.
- At the start of a session, also delete any other `claude/...` branches whose work is already on the default branch (merged, or rebuilt into a later commit there). Check each one first (`git merge-base --is-ancestor`, or compare the files it changed); keep any branch with work that isn't on the default branch, and say so to the person you are working with.
- Never delete the repository's default branch.
- `.claude/settings.json` allows `git push origin --delete`, so this needs no approval.
