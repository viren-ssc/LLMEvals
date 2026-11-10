# Git setup and credentials

Git is initialized locally on `main`. The initial files are grouped into purpose-specific commits at the user's request. No remote or push is configured automatically.

## Review and push

Choose a repository with the intended access restrictions: supplied benchmark answers and reference evidence are included in Git-visible data. Runtime result folders under `outputs/` are deliberately excluded and must be transferred separately when needed.

```powershell
.\.venv\Scripts\python.exe scripts\check_git_secrets.py
git status --short
git log --oneline
# For subsequent changes only:
git add path/to/changed_file
git diff --cached --stat
git commit -m "Describe the specific change"
# Replace this placeholder with your actual repository URL:
git remote add origin "YOUR_REPOSITORY_URL"
git push -u origin main
```

If Git asks for identity, configure your own real `user.name` and `user.email`; no identity is invented by this setup. Authenticate using your approved Git credential manager or SSH agent. Never put tokens in a remote URL or commit message.

## Pull onto HPC

```bash
git clone YOUR_REPOSITORY_URL LLMEvals
cd LLMEvals
# Later updates:
git pull --ff-only
```

HPC can hold the code and data, but cannot reach this project's icelab judge. Evaluation still runs on an authorized normal desktop. Git does not transfer `.env`, `.venv` or ignored result files. Create a fresh environment and credential file only on the authorized judging desktop.

## Protections and limits

- `.gitignore` excludes environment secrets, common credential directories, private keys, cloud/SSH state, local editor/agent state, caches, databases, logs and runtime results.
- Only the reviewed blank `.env.example` is intentionally included.
- `.gitattributes` disables line-ending normalization because frozen experiment hashes bind exact bytes. Do not remove that setting casually.
- `scripts/check_git_secrets.py` checks tracked and untracked nonignored files for known local `.env` secrets and recognizable token/private-key patterns. It prints paths and counts, never matched values. It cannot guarantee detection of every secret or inspect Git history.
- Ignore rules do not remove secrets already committed. If one is accidentally committed, revoke/rotate it first and clean history before sharing. Do not rely on deleting it in a later commit.

A local setup check found zero suspected-secret files among 314 Git-visible files before this documentation page was added. Re-run the scanner before each push; review the staged file list as well.
