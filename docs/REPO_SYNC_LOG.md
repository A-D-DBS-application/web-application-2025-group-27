## Repository sync log

- **Date**: 2025-12-01
- **Action**: Configure shared group remote and push code.
- **Details**:
  - Added/updated remote `group` → `git@github.com:A-D-DBS-application/web-application-2025-group-27.git`.
  - Attempted `git push group main`.
  - Push was **rejected** with `non-fast-forward` because the remote `main` branch already has commits that your local `main` is behind.
- **Follow-up on 2025-12-01**:
  - Decision: **Force overwrite** the group repository `main` with the local `main`.
  - Command executed: `git push --force group main`.
  - Result: Push completed successfully (`main -> main (forced update)`); the group repo’s `main` now matches the local `Rival` repository state.

### How to push to each repo (short)

- **Push to your own repo only (GitHub `JeanKnecht/Rival`)**: `git push origin main`
- **Push to the group repo only (GitHub Classroom repo)**: `git push group main`
- **Push to both manually in one go**: `git push origin main && git push group main`

### Recommended workflow (sandbox vs. source of truth)

- **Your repo (`origin`)**: use as a **sandbox** – experiment on branches, push WIP, and iterate freely.
- **Group repo (`group`)**: treat as **source of truth** – only push stable `main` changes you’re happy to share with the team.
- To restore local `main` from the group repo if needed:  
  `git fetch group && git reset --hard group/main`
- To push a **stable `main`** to the group repo (source of truth):  
  `git push group main`
