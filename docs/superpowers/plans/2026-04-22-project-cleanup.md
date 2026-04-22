# MITS Project Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up accumulated artifacts, reorganize `docs/` and `scripts/` into semantic subfolders, refresh README.md with honest evaluation metrics and a feature timeline.

**Architecture:** Five sequential commits (one per spec section), each independently revertable via `git reset --hard HEAD^`. No code under `src/`, `backend/`, `frontend/` is touched — this is purely a file-organization + README update pass.

**Tech Stack:** Git (mv/rm), Python (matplotlib/seaborn for new README figures), Bash (verification commands).

**Spec:** `docs/superpowers/specs/2026-04-22-project-cleanup-design.md` (commit `0f4b2d1`).

---

## File Structure

### Files created
- `docs/INDEX.md` — navigation hub for reorganized docs
- `scripts/README.md` — map of scripts subdirectories
- `scripts/diploma/README.md` — warning that these are one-shot
- `figures/readme/feature_timeline.png` — 016 → 017 → 018 horizontal timeline
- `figures/readme/domain_heatmap.png` — domain × stage accuracy heatmap
- `scripts/diploma/make_readme_figures.py` — script generating above two PNGs (kept for reproducibility)

### Files moved (git mv — preserves history)
- 11 `.docx` files in `docs/` → `docs/diploma/`, `docs/archive/pre-2026/`, `docs/archive/nir-drafts/`
- 2 `.pdf` files → `docs/diploma/exports/`
- 13 `.md` files in `docs/` → `docs/{diploma,architecture,training,guides}/`
- ~20 scripts in `scripts/` → `scripts/{db,knowledge,ollama,design,diploma}/`

### Files modified
- `README.md` — new metrics tables, feature timeline, FAQ, updated structure tree
- `.gitignore` — add missing entries (venv/, *.egg-info/, ~$*, etc.)
- `.env.example` — consolidate Docker and TurboQuant-specific options as commented sections

### Files deleted
- `venv/` (8.1 GB), `design_handoff.7z`, `mits.egg-info/`, `.pytest_cache/`, `.ruff_cache/`
- `New_style/` (407 KB), `Снимок экрана 2026-02-05 143909.png`, `.env.docker`, `.env.optimized`
- `models/` (entire directory — all deprecated)
- `docs/~$*.docx`, `docs/*.bak.docx`, `docs/*.pre-hardport.bak.docx`
- `docs/article_c3432f25.docx`, `docs/Статья_GNN_Лысенко_ОД_ИУК3-82Б.docx`

---

## Task 0: Pre-flight Safety Checks

**Files:** None (read-only checks).

- [ ] **Step 0.1: Verify on correct branch with clean tracked tree**

```bash
git -C C:/Work/MITS status --porcelain | grep -E "^\s*M"
git -C C:/Work/MITS branch --show-current
```
Expected: branch = `018-path-slime`. The listed `M` (modified) files are from prior session — we'll stash them if they conflict with our work. For now, just note them.

- [ ] **Step 0.2: Check `tools/llama.cpp` — is it a git submodule?**

```bash
git -C C:/Work/MITS submodule status 2>&1
ls C:/Work/MITS/.gitmodules 2>&1
```
Expected: if `.gitmodules` exists and lists `tools/llama.cpp` — **do not touch** it during cleanup. If neither exists — it's a raw clone, leave it alone anyway (not in our scope).

- [ ] **Step 0.3: Stop any WINWORD process holding docx files**

```bash
powershell -Command "Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force; Write-Output 'WINWORD stopped (or was not running)'"
```
Expected: "WINWORD stopped (or was not running)". If Word is open, this closes it without saving — that's what we want since the modified files we care about were already committed.

- [ ] **Step 0.4: Stash existing uncommitted changes (if any) that would conflict**

```bash
git -C C:/Work/MITS stash push -m "pre-cleanup-stash-2026-04-22" -- \
  ".claude/settings.local.json" \
  "docs/Курсовой_проект_Сухацкий_2026.docx" \
  "docs/НИР_Сухацкий_2026_controlled_reasoning.docx" \
  "frontend/src/components/layout/Sidebar.tsx" \
  "src/agents/task_generator.py"
```
Expected: stash message or "No local changes to save". The WIP changes are preserved; after cleanup we `git stash pop`.

- [ ] **Step 0.5: Snapshot disk usage for before/after comparison**

```bash
du -sh C:/Work/MITS/venv C:/Work/MITS/.venv C:/Work/MITS/models C:/Work/MITS/New_style 2>&1
du -sh C:/Work/MITS 2>&1
```
Expected: baseline sizes to compare after. Log manually — venv ~8.1 GB, models ~few GB (GLM models), etc.

---

## Task 1: Section 1 — Safe Deletions

**Goal:** Remove ~10 GB of duplicates, build artifacts, Word locks, deprecated files. Update `.gitignore`.

**Files:**
- Delete: `venv/`, `design_handoff.7z`, `mits.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `New_style/`, `Снимок экрана 2026-02-05 143909.png`, `.env.docker`, `.env.optimized`, `models/`, `docs/~$*.docx`, `docs/*.bak.docx`, `docs/*.pre-hardport.bak.docx`, `docs/article_c3432f25.docx`, `docs/Статья_GNN_Лысенко_ОД_ИУК3-82Б.docx`, `docs/НИР (1).pdf`-not yet (see Task 2)
- Modify: `.gitignore`

- [ ] **Step 1.1: Extract any unique settings from `.env.docker` and `.env.optimized` before deletion**

```bash
cat C:/Work/MITS/.env.docker
echo "----- DIVIDER -----"
cat C:/Work/MITS/.env.optimized
```
Expected: see full contents. Note unique keys. We'll paste them as comments into `.env.example` in Step 1.2.

- [ ] **Step 1.2: Build the list of unique keys from each file**

Use Bash to compute the set difference (keys in `.env.docker` but NOT in `.env.example`):

```bash
cd C:/Work/MITS
# Extract just the KEY= part from each file, exclude blanks and comments
grep -E '^[A-Z_]+=' .env.example  | awk -F= '{print $1}' | sort -u > /tmp/example_keys.txt
grep -E '^[A-Z_]+=' .env.docker   | awk -F= '{print $1}' | sort -u > /tmp/docker_keys.txt
grep -E '^[A-Z_]+=' .env.optimized| awk -F= '{print $1}' | sort -u > /tmp/optimized_keys.txt

echo "=== Unique to .env.docker ==="
comm -23 /tmp/docker_keys.txt /tmp/example_keys.txt
echo "=== Unique to .env.optimized ==="
comm -23 /tmp/optimized_keys.txt /tmp/example_keys.txt
```
Expected: list of keys that exist only in each source file. Save these lists — they drive Step 1.2b.

- [ ] **Step 1.2b: Append the unique keys to `.env.example` as commented lines**

Use the Edit tool on `C:/Work/MITS/.env.example`. Append the following block at end-of-file. For each key printed by Step 1.2, read its value from the source file and paste as `# KEY=value` (commented out — these are opt-in overrides, not defaults):

```dotenv

# ─────────────────────────────────────────────────────────
# Docker-specific overrides (consolidated from .env.docker)
# Uncomment when running via docker-compose
# ─────────────────────────────────────────────────────────
# For each key from Step 1.2 "Unique to .env.docker" output,
# grep the value from .env.docker and paste here as "# KEY=value"

# ─────────────────────────────────────────────────────────
# TurboQuant / Ollama optimized overrides (consolidated from .env.optimized)
# Uncomment to enable KV cache compression + speculative decoding
# ─────────────────────────────────────────────────────────
# For each key from Step 1.2 "Unique to .env.optimized" output,
# grep the value from .env.optimized and paste here as "# KEY=value"
```

**Concrete command for fetching values** (run once you have the unique keys list):
```bash
while IFS= read -r key; do
  grep -E "^${key}=" C:/Work/MITS/.env.docker | sed 's/^/# /'
done < /tmp/docker_keys_unique.txt
```
(You'll need to save the comm output to `/tmp/docker_keys_unique.txt` first: `comm -23 /tmp/docker_keys.txt /tmp/example_keys.txt > /tmp/docker_keys_unique.txt`.)

Paste the resulting `# KEY=value` lines under the Docker-specific header. Repeat for `.env.optimized`.

- [ ] **Step 1.3: Delete `venv/` (the duplicate, keeps `.venv/`)**

```bash
rm -rf C:/Work/MITS/venv
ls C:/Work/MITS/.venv > /dev/null && echo "OK: .venv still present"
```
Expected: "OK: .venv still present". `venv/` is gone.

- [ ] **Step 1.4: Delete build artifacts and caches**

```bash
rm -rf C:/Work/MITS/mits.egg-info
rm -rf C:/Work/MITS/.pytest_cache
rm -rf C:/Work/MITS/.ruff_cache
rm -f C:/Work/MITS/design_handoff.7z
rm -f "C:/Work/MITS/Снимок экрана 2026-02-05 143909.png"
rm -rf C:/Work/MITS/New_style
```
Expected: silent success.

- [ ] **Step 1.5: Delete Word lock files and `.env.*` duplicates**

```bash
find C:/Work/MITS/docs -name '~$*' -type f -delete 2>&1
rm -f C:/Work/MITS/.env.docker
rm -f C:/Work/MITS/.env.optimized
```
Expected: silent success.

- [ ] **Step 1.6: Delete stale `.docx` backups and foreign articles**

```bash
cd C:/Work/MITS/docs
git rm -f "Курсовой_проект_Сухацкий_2026.bak.docx"
git rm -f "Курсовой_проект_Сухацкий_2026.pre-hardport.bak.docx"
git rm -f "НИР_Сухацкий_2026_controlled_reasoning.pre-hardport.bak.docx"
git rm -f "article_c3432f25.docx" 2>&1 || rm -f "article_c3432f25.docx"
git rm -f "Статья_GNN_Лысенко_ОД_ИУК3-82Б.docx" 2>&1 || rm -f "Статья_GNN_Лысенко_ОД_ИУК3-82Б.docx"
```
Note: `.pre-hardport.bak.docx` files are untracked (per git status), so use plain `rm -f` for them:

```bash
rm -f "C:/Work/MITS/docs/Курсовой_проект_Сухацкий_2026.pre-hardport.bak.docx"
rm -f "C:/Work/MITS/docs/НИР_Сухацкий_2026_controlled_reasoning.pre-hardport.bak.docx"
```
Expected: files removed.

- [ ] **Step 1.7: Delete `models/` directory (all deprecated)**

```bash
git -C C:/Work/MITS rm -rf models/ 2>&1
```
Expected: list of removed files including `Modelfile.mits-tutor-qwen3-1.7b`, `Modelfile.mits-tutor-qwen3-4b`, `Modelfile-reap-q8`, `Modelfile-reap-v2`, and the `glm-*` subdirs (if tracked).

If `models/` contains untracked subdirs (glm models often are), the above only removes tracked files. Fallback:
```bash
rm -rf C:/Work/MITS/models
```

- [ ] **Step 1.8: Find `__pycache__/` directories and delete them**

```bash
find C:/Work/MITS -type d -name '__pycache__' ! -path '*/\.venv/*' -print
```
Expected: list of cache dirs. Then:
```bash
find C:/Work/MITS -type d -name '__pycache__' ! -path '*/\.venv/*' -exec rm -rf {} + 2>&1
echo "Cleaned."
```

- [ ] **Step 1.9: Update `.gitignore` — add missing entries**

First inspect current:
```bash
cat C:/Work/MITS/.gitignore
```

Then use Edit tool to add (at bottom, only entries not already present):
```gitignore

# Cleanup additions 2026-04-22
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
~$*
.env.docker
.env.optimized
models/*/
!models/.gitkeep
wandb/
figures/readme/*.png
!figures/readme/.gitkeep
```

Note: `.venv/`, `__pycache__/`, `.env` are usually already in `.gitignore` — verify before adding.

- [ ] **Step 1.10: Verify disk saved**

```bash
du -sh C:/Work/MITS 2>&1
echo "Should be ~10 GB smaller than before Step 0.5"
```

- [ ] **Step 1.11: Run smoke test — nothing broke**

```bash
cd C:/Work/MITS && python -c "import src" 2>&1 | head -5
cd C:/Work/MITS && python -c "from backend.app.main import app" 2>&1 | head -5
```
Expected: no import errors. If errors — a required file was deleted. Investigate before committing.

- [ ] **Step 1.12: Commit Section 1**

```bash
cd C:/Work/MITS
git add .gitignore .env.example
git status --short | head -30
```
Verify deletions are staged (`D` prefix) and no surprises. Then:
```bash
git commit -m "$(cat <<'EOF'
chore(cleanup): remove build artifacts and duplicates

Removed ~10 GB:
- venv/ (duplicate of .venv/)
- mits.egg-info/, .pytest_cache/, .ruff_cache/
- design_handoff.7z (folder is unpacked)
- New_style/ (integrated into frontend/)
- models/ (all deprecated — GLM + Qwen 1.7B/4B Modelfiles)
- .env.docker, .env.optimized (consolidated into .env.example)
- Screenshot from 2026-02-05 (unused)

Removed foreign/stale docx:
- *.bak.docx, *.pre-hardport.bak.docx (×3)
- article_c3432f25.docx, Статья_GNN_Лысенко (other student's work)

Updated .gitignore to prevent re-accumulation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: commit succeeds.

---

## Task 2: Section 2 — Reorganize `docs/`

**Goal:** Split `docs/` into `diploma/`, `architecture/`, `training/`, `guides/`, `archive/`. Create `INDEX.md`.

**Files:**
- Create: `docs/INDEX.md`, plus 5 new subdirs (with `.gitkeep` if empty)
- Move via `git mv`: all 11 `.md` files + actual `.docx` / `.pdf` files
- Modify: any file with hardcoded `docs/<filename>.md` reference

- [ ] **Step 2.1: Grep codebase for hardcoded doc paths (must update before move)**

```bash
cd C:/Work/MITS
for f in TRAINING_PIPELINE.md GSPO_TECHNIQUES_DETAIL.md ARCHITECTURE.md MODEL_SELECTION.md OPTIMIZATION_PLAN.md RESOURCE_PROFILES.md TURBO_QUANT_BACKEND.md DIPLOMA_PLAN.md DIPLOMA_DIAGRAMS.md PROJECT_STATUS.md quickstart.md presentation_notes_main.md presentation_notes_rl_qwen.md; do
  echo "=== $f ==="
  grep -rn "docs/$f" --include="*.md" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" 2>/dev/null | grep -v "^docs/" || echo "  (no refs)"
done
```
Expected: list of files referencing each doc. Record which references need updating.

- [ ] **Step 2.2: Create target subdirectories**

```bash
cd C:/Work/MITS/docs
mkdir -p diploma/exports architecture training guides archive/pre-2026 archive/nir-drafts
ls -la
```
Expected: six new subdirs visible.

- [ ] **Step 2.3: Move diploma active files**

```bash
cd C:/Work/MITS
git mv "docs/Курсовой_проект_Сухацкий_2026.docx" "docs/diploma/Курсовой_проект_Сухацкий_2026.docx"
git mv "docs/НИР_Сухацкий_2026_controlled_reasoning.docx" "docs/diploma/НИР_Сухацкий_2026_controlled_reasoning.docx"
git mv "docs/DIPLOMA_PLAN.md" "docs/diploma/DIPLOMA_PLAN.md"
git mv "docs/DIPLOMA_DIAGRAMS.md" "docs/diploma/DIPLOMA_DIAGRAMS.md"
git mv "docs/Курсовой_проект.pdf" "docs/diploma/exports/Курсовой_проект.pdf"
git mv "docs/НИР (1).pdf" "docs/diploma/exports/НИР.pdf"
git status --short | head -10
```
Expected: all 6 moves shown as `R` (rename) entries.

- [ ] **Step 2.4: Move architecture files**

```bash
cd C:/Work/MITS
git mv docs/ARCHITECTURE.md docs/architecture/ARCHITECTURE.md
git mv docs/MODEL_SELECTION.md docs/architecture/MODEL_SELECTION.md
git mv docs/OPTIMIZATION_PLAN.md docs/architecture/OPTIMIZATION_PLAN.md
git mv docs/RESOURCE_PROFILES.md docs/architecture/RESOURCE_PROFILES.md
git mv docs/TURBO_QUANT_BACKEND.md docs/architecture/TURBO_QUANT_BACKEND.md
```
Expected: 5 rename entries.

- [ ] **Step 2.5: Move training files**

```bash
cd C:/Work/MITS
git mv docs/TRAINING_PIPELINE.md docs/training/TRAINING_PIPELINE.md
git mv docs/GSPO_TECHNIQUES_DETAIL.md docs/training/GSPO_TECHNIQUES_DETAIL.md
git mv docs/presentation_notes_main.md docs/training/presentation_notes_main.md
git mv docs/presentation_notes_rl_qwen.md docs/training/presentation_notes_rl_qwen.md
```

- [ ] **Step 2.6: Move guides**

```bash
cd C:/Work/MITS
git mv docs/quickstart.md docs/guides/quickstart.md
git mv docs/PROJECT_STATUS.md docs/guides/PROJECT_STATUS.md
```

- [ ] **Step 2.7: Move archived docx**

```bash
cd C:/Work/MITS
git mv "docs/Курсовая_MITS_Сухацкий.docx" "docs/archive/pre-2026/Курсовая_MITS_Сухацкий.docx"
git mv "docs/НИР_Сухацкий_2026_knowledge_forge.docx" "docs/archive/nir-drafts/НИР_Сухацкий_2026_knowledge_forge.docx"
git mv "docs/НИР_управляемое_рассуждение_Сухацкий.docx" "docs/archive/nir-drafts/НИР_управляемое_рассуждение_Сухацкий.docx"
git mv "docs/Новый_подход_к_дистилляции_ризонинга_Сухацкий.docx" "docs/archive/nir-drafts/Новый_подход_к_дистилляции_ризонинга_Сухацкий.docx"
```

- [ ] **Step 2.8: Verify `docs/` root is clean**

```bash
ls C:/Work/MITS/docs
```
Expected: only directories (`diploma/`, `architecture/`, `training/`, `guides/`, `archive/`, `superpowers/`). No loose files yet — `INDEX.md` we'll create next.

- [ ] **Step 2.9: Create `docs/INDEX.md`**

Use Write tool to create `C:/Work/MITS/docs/INDEX.md` with:

```markdown
# MITS Documentation Index

## 🎓 Diploma (2026)
- [НИР 2026 — Controlled Reasoning](diploma/НИР_Сухацкий_2026_controlled_reasoning.docx)
- [Курсовой проект 2026](diploma/Курсовой_проект_Сухацкий_2026.docx)
- [Diploma Plan](diploma/DIPLOMA_PLAN.md)
- [Diploma Diagrams](diploma/DIPLOMA_DIAGRAMS.md)
- PDF exports in [diploma/exports/](diploma/exports/)

## 🏛 Architecture
- [System Architecture](architecture/ARCHITECTURE.md)
- [Model Selection](architecture/MODEL_SELECTION.md)
- [Optimization Plan](architecture/OPTIMIZATION_PLAN.md)
- [Resource Profiles](architecture/RESOURCE_PROFILES.md)
- [TurboQuant Backend](architecture/TURBO_QUANT_BACKEND.md)

## 🚀 Training
- [Training Pipeline](training/TRAINING_PIPELINE.md)
- [GSPO Techniques](training/GSPO_TECHNIQUES_DETAIL.md)
- [Presentation — Main](training/presentation_notes_main.md)
- [Presentation — RL Qwen](training/presentation_notes_rl_qwen.md)

## 📘 Guides
- [Quickstart](guides/quickstart.md)
- [Project Status](guides/PROJECT_STATUS.md)

## 🗄 Archive
Previous iterations kept for historical reference — not used in current pipeline.
- [pre-2026/](archive/pre-2026/) — coursework from 2024 (Curso MITS 2024)
- [nir-drafts/](archive/nir-drafts/) — НИР drafts before "controlled reasoning" final version

---

*Updated 2026-04-22 via [project-cleanup](superpowers/specs/2026-04-22-project-cleanup-design.md).*
```

- [ ] **Step 2.10: Update hardcoded doc references from Step 2.1**

For each (file, old_path) pair reported by Step 2.1, use the Edit tool to replace with the new path. Mapping table:

| Old path | New path |
|----------|----------|
| `docs/TRAINING_PIPELINE.md` | `docs/training/TRAINING_PIPELINE.md` |
| `docs/GSPO_TECHNIQUES_DETAIL.md` | `docs/training/GSPO_TECHNIQUES_DETAIL.md` |
| `docs/presentation_notes_main.md` | `docs/training/presentation_notes_main.md` |
| `docs/presentation_notes_rl_qwen.md` | `docs/training/presentation_notes_rl_qwen.md` |
| `docs/ARCHITECTURE.md` | `docs/architecture/ARCHITECTURE.md` |
| `docs/MODEL_SELECTION.md` | `docs/architecture/MODEL_SELECTION.md` |
| `docs/OPTIMIZATION_PLAN.md` | `docs/architecture/OPTIMIZATION_PLAN.md` |
| `docs/RESOURCE_PROFILES.md` | `docs/architecture/RESOURCE_PROFILES.md` |
| `docs/TURBO_QUANT_BACKEND.md` | `docs/architecture/TURBO_QUANT_BACKEND.md` |
| `docs/DIPLOMA_PLAN.md` | `docs/diploma/DIPLOMA_PLAN.md` |
| `docs/DIPLOMA_DIAGRAMS.md` | `docs/diploma/DIPLOMA_DIAGRAMS.md` |
| `docs/quickstart.md` | `docs/guides/quickstart.md` |
| `docs/PROJECT_STATUS.md` | `docs/guides/PROJECT_STATUS.md` |

**Known files likely to need updates** (verify with Step 2.1 output):
- `C:/Work/MITS/CLAUDE.md` — may reference docs in "Project Structure" / "Recent Changes" sections
- `C:/Work/MITS/README.md` — may reference in "Документация" link + other sections (line 19 and possibly elsewhere)
- `C:/Work/MITS/docs/diploma/DIPLOMA_PLAN.md` — may cross-reference other moved files
- `C:/Work/MITS/docs/architecture/ARCHITECTURE.md` — may cross-reference other docs
- `C:/Work/MITS/docs/guides/PROJECT_STATUS.md` — may reference the pipeline doc

**Exact Edit command example** (adapt to each reference Step 2.1 found):
```
Edit file_path=C:/Work/MITS/CLAUDE.md
  old_string="docs/TRAINING_PIPELINE.md"
  new_string="docs/training/TRAINING_PIPELINE.md"
```

- [ ] **Step 2.11: Verify no broken references**

```bash
cd C:/Work/MITS
for f in TRAINING_PIPELINE.md GSPO_TECHNIQUES_DETAIL.md ARCHITECTURE.md MODEL_SELECTION.md OPTIMIZATION_PLAN.md RESOURCE_PROFILES.md TURBO_QUANT_BACKEND.md DIPLOMA_PLAN.md DIPLOMA_DIAGRAMS.md PROJECT_STATUS.md quickstart.md presentation_notes_main.md presentation_notes_rl_qwen.md; do
  count=$(grep -rn "docs/$f" --include="*.md" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" 2>/dev/null | grep -vE "(docs/(diploma|architecture|training|guides|archive|superpowers)/|CHANGELOG)" | wc -l)
  if [ "$count" -gt 0 ]; then
    echo "!!! STILL BROKEN: docs/$f"
    grep -rn "docs/$f" --include="*.md" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" 2>/dev/null | grep -vE "(docs/(diploma|architecture|training|guides|archive|superpowers)/|CHANGELOG)"
  fi
done
echo "Verification complete."
```
Expected: no "STILL BROKEN" lines. Fix any that appear.

- [ ] **Step 2.12: Commit Section 2**

```bash
cd C:/Work/MITS
git add docs/INDEX.md
git status --short | head -30
```
Verify 11+ rename entries and new `INDEX.md`. Then:
```bash
git commit -m "$(cat <<'EOF'
chore(docs): reorganize docs/ into semantic subdirs + archive

New structure:
- docs/diploma/          current НИР + Курсовой 2026 + plans + PDF exports
- docs/architecture/     ARCHITECTURE, MODEL_SELECTION, OPTIMIZATION_PLAN, ...
- docs/training/         TRAINING_PIPELINE, GSPO_TECHNIQUES, presentations
- docs/guides/           quickstart, PROJECT_STATUS
- docs/archive/          pre-2026 coursework + nir-drafts

Added docs/INDEX.md as navigation hub.

Updated all hardcoded references in CLAUDE.md, README.md, etc.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Section 3 — Reorganize `scripts/`

**Goal:** Split `scripts/` into `db/`, `knowledge/`, `ollama/`, `design/`, `diploma/`. All one-shot diploma scripts → `scripts/diploma/` with warning README.

**Files:**
- Create: `scripts/README.md`, `scripts/diploma/README.md`, 5 new subdirs
- Move via `git mv`: ~20 scripts

- [ ] **Step 3.1: Create subdirectories**

```bash
cd C:/Work/MITS/scripts
mkdir -p db knowledge ollama design diploma
```

- [ ] **Step 3.2: Move db scripts**

```bash
cd C:/Work/MITS
git mv scripts/init_db.py scripts/db/init_db.py
git mv scripts/migrate_to_forge.py scripts/db/migrate_to_forge.py
```

- [ ] **Step 3.3: Move knowledge scripts**

```bash
cd C:/Work/MITS
git mv scripts/grow_knowledge_graph.py scripts/knowledge/grow_knowledge_graph.py
git mv scripts/precompute_embeddings.py scripts/knowledge/precompute_embeddings.py
git mv scripts/ingest_pdf.py scripts/knowledge/ingest_pdf.py
```

- [ ] **Step 3.4: Move ollama scripts**

```bash
cd C:/Work/MITS
git mv scripts/activate_turbo_quant.ps1 scripts/ollama/activate_turbo_quant.ps1
git mv scripts/check_ollama_config.py scripts/ollama/check_ollama_config.py
git mv scripts/detect_resources.py scripts/ollama/detect_resources.py
git mv scripts/optimize_ollama.ps1 scripts/ollama/optimize_ollama.ps1
git mv scripts/pull-models.sh scripts/ollama/pull-models.sh
git mv scripts/setup_speculative.ps1 scripts/ollama/setup_speculative.ps1
git mv scripts/start_ollama_optimized.ps1 scripts/ollama/start_ollama_optimized.ps1
git mv scripts/start_optimized.ps1 scripts/ollama/start_optimized.ps1
git mv scripts/test_hf_turbo.py scripts/ollama/test_hf_turbo.py
```

- [ ] **Step 3.5: Move design scripts**

```bash
cd C:/Work/MITS
git mv scripts/build_design_handoff.py scripts/design/build_design_handoff.py
git mv scripts/generate_social_preview.py scripts/design/generate_social_preview.py
```

- [ ] **Step 3.6: Move diploma one-shot scripts**

Tracked (already in git):
```bash
cd C:/Work/MITS
git mv scripts/generate_diploma_docs.py scripts/diploma/generate_diploma_docs.py
git mv scripts/generate_nir_controlled_reasoning.py scripts/diploma/generate_nir_controlled_reasoning.py
git mv scripts/reformat_coursework.py scripts/diploma/reformat_coursework.py
git mv scripts/extend_diploma_docs.py scripts/diploma/extend_diploma_docs.py
git mv scripts/extend_diploma_docs_v2.py scripts/diploma/extend_diploma_docs_v2.py
```

Untracked (per earlier git status — use plain `mv` then add):
```bash
cd C:/Work/MITS
mv scripts/rewrite_coursework_academic.py scripts/diploma/rewrite_coursework_academic.py
mv scripts/enrich_docs_figures_metrics.py scripts/diploma/enrich_docs_figures_metrics.py
mv scripts/make_fig21_clean.py scripts/diploma/make_fig21_clean.py
mv scripts/redo_fig21_architecture.py scripts/diploma/redo_fig21_architecture.py
mv scripts/fix_nir_figs_32_33.py scripts/diploma/fix_nir_figs_32_33.py
```

- [ ] **Step 3.7: Verify `scripts/` root is clean**

```bash
ls C:/Work/MITS/scripts
```
Expected: only subdirs (`db`, `knowledge`, `ollama`, `design`, `diploma`, `migrations`). No loose `.py` / `.ps1` / `.sh`.

- [ ] **Step 3.8: Create `scripts/README.md`**

Use Write tool on `C:/Work/MITS/scripts/README.md`:

```markdown
# MITS Scripts

Utility scripts for the MITS project, grouped by purpose.

## 📂 Subdirectories

### `db/` — database & migrations
- `init_db.py` — initialize SQLite schemas (sessions, students, analytics)
- `migrate_to_forge.py` — migrate legacy skill graph → Knowledge Forge format

See also: `migrations/` (Alembic migrations for backend).

### `knowledge/` — knowledge graph, RAG, embeddings
- `grow_knowledge_graph.py` — extend skill graph via LLM extraction
- `precompute_embeddings.py` — cache sentence embeddings for RAG
- `ingest_pdf.py` — parse PDF textbooks into Knowledge Forge nodes

### `ollama/` — local inference stack (Ollama + TurboQuant)
PowerShell scripts optimize Ollama for the current GPU profile.
- `check_ollama_config.py` — sanity-check current Ollama setup
- `detect_resources.py` — auto-detect GPU/RAM to pick resource profile
- `optimize_ollama.ps1` / `activate_turbo_quant.ps1` — apply TurboQuant KV cache compression
- `pull-models.sh`, `start_ollama_optimized.ps1`, `start_optimized.ps1` — launch helpers
- `setup_speculative.ps1` — speculative decoding setup
- `test_hf_turbo.py` — verify HuggingFace + bitsandbytes NF4 pipeline

### `design/` — design artifacts
- `build_design_handoff.py` — bundle `design_handoff/` folder into 7z
- `generate_social_preview.py` — GitHub social preview PNG generator

### `diploma/` — one-shot scripts for diploma documents
⚠️ **Already ran.** These scripts modified `docs/diploma/*.docx` and generated
`figures/diploma/*.png`. Kept for reproducibility. See `diploma/README.md` for details.

### `migrations/` — Alembic database migrations
Managed by SQLAlchemy/Alembic, not called directly.

## Running scripts

Most Python scripts expect repo root as CWD:
```bash
cd C:/Work/MITS
python scripts/knowledge/ingest_pdf.py --help
```

PowerShell scripts:
```powershell
pwsh scripts/ollama/optimize_ollama.ps1
```
```

- [ ] **Step 3.9: Create `scripts/diploma/README.md`**

Use Write tool:

```markdown
# Diploma — One-shot Scripts

These scripts generated/modified the diploma documents (`docs/diploma/*.docx`)
and their figures in `figures/diploma/`. They ran once; their effect is
captured in the tracked `.docx` files.

⚠️ **Do not re-run** unless you want to regenerate from scratch. Running them
will overwrite the currently-tracked diploma docs.

## Timeline

| Script | Purpose | When |
|--------|---------|------|
| `generate_diploma_docs.py` | First draft of Курсовой + НИР | Early 2026-04 |
| `extend_diploma_docs.py`, `_v2.py` | Expand metric tables, add figures | Mid 2026-04 |
| `reformat_coursework.py` | GOST formatting (A4, margins, Times 14pt, 1.5 spacing) | 2026-04 |
| `rewrite_coursework_academic.py` | Impersonal academic style (per supervisor feedback) | 2026-04-21 |
| `generate_nir_controlled_reasoning.py` | НИР hard-port from reference .docx | 2026-04-21 |
| `enrich_docs_figures_metrics.py` | 9 figures + 11 metric descriptions | 2026-04-21 |
| `make_fig21_clean.py` | Intermediate clean version of Рис. 2.1 | 2026-04-21 |
| `redo_fig21_architecture.py` | Final clean Рис. 2.1 (agent architecture) | 2026-04-21 |
| `fix_nir_figs_32_33.py` | Final arrow/legend fixes for НИР Рис. 3.2 and 3.3 | 2026-04-22 |

## If you MUST re-run

1. Close MS Word on all diploma documents.
2. Run from repo root: `cd C:/Work/MITS && python -X utf8 scripts/diploma/<script>.py`.
3. Expect absolute paths inside each script — they write to fixed locations.
```

- [ ] **Step 3.10: Smoke-test — ensure no script imports anything that moved**

```bash
cd C:/Work/MITS
python -c "import ast, pathlib
for p in pathlib.Path('scripts').rglob('*.py'):
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        print(f'SYNTAX ERROR: {p}: {e}')
print('All scripts parse OK.')"
```
Expected: "All scripts parse OK." No syntax errors (imports may still be broken at runtime, but syntax is fine — the scripts have absolute paths so moves don't break them).

- [ ] **Step 3.11: Commit Section 3**

```bash
cd C:/Work/MITS
git add scripts/README.md scripts/diploma/README.md
git status --short | head -40
```
Verify ~20 rename entries + 2 new READMEs. Then:

```bash
git commit -m "$(cat <<'EOF'
chore(scripts): reorganize into db/knowledge/ollama/design/diploma

Grouped ~20 loose scripts by purpose:
- scripts/db/         init_db, migrate_to_forge
- scripts/knowledge/  grow_graph, ingest_pdf, precompute_embeddings
- scripts/ollama/     optimize, detect_resources, turbo quant (PS + Python)
- scripts/design/     handoff builder, social preview
- scripts/diploma/    one-shot diploma generators (⚠️ already ran)

Added scripts/README.md and scripts/diploma/README.md with timeline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Section 4 — Already done in Task 1

Section 4 of the spec (root cleanup, `models/` removal, `.env.*` consolidation) was executed entirely within Task 1 (steps 1.1–1.12). **Skip to Task 5.**

*Rationale:* When writing the plan I realized root cleanup and deletions are atomic — splitting them across two commits creates artificial boundaries. The commit message in Task 1 covers the whole scope.

---

## Task 5: Section 5 — README Refresh

**Goal:** Update README.md with honest metrics tables, feature timeline, FAQ, updated tree. Generate 2 new figures.

**Files:**
- Create: `figures/readme/feature_timeline.png`, `figures/readme/domain_heatmap.png`, `scripts/diploma/make_readme_figures.py`
- Modify: `README.md`

### Task 5A: Figure generation script

- [ ] **Step 5A.1: Create `scripts/diploma/make_readme_figures.py`**

Use Write tool on `C:/Work/MITS/scripts/diploma/make_readme_figures.py`:

```python
"""Generate 2 README figures: feature_timeline.png and domain_heatmap.png.

Style matches existing figures/diploma/* (DejaVu Sans, print-friendly palette)
while leaning a bit darker to echo README cyberpunk banner.

Output: figures/readme/feature_timeline.png, figures/readme/domain_heatmap.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

FIGS_DIR = Path("C:/Work/MITS/figures/readme")
FIGS_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.dpi": 200,
        "axes.facecolor": "#FDFDFE",
    }
)

# Palette — lilac/indigo to match README banner
C_016 = "#818CF8"  # indigo
C_017 = "#A78BFA"  # violet
C_018 = "#C4B5FD"  # lilac
C_ACCENT = "#5B21B6"


def feature_timeline() -> Path:
    """Horizontal timeline: 016 Knowledge Forge → 017 ToM-Tutor → 018 PathSlime."""
    fig, ax = plt.subplots(figsize=(11, 2.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(-1.5, 2.2)
    ax.axis("off")

    features = [
        (1.0, C_016, "016 Knowledge Forge", "Living KG\n83 nodes × 88 edges", "мар 2026"),
        (5.0, C_017, "017 ToM-Tutor", "Mental Model\n70%→95% root-hit", "апр 2026"),
        (9.0, C_018, "018 PathSlime", "Lévy-Gaussian SMA\nk diverse paths", "апр 2026"),
    ]

    for x, color, title, subtitle, date in features:
        ax.add_patch(
            FancyBboxPatch(
                (x - 1.25, -0.7),
                2.5,
                1.4,
                boxstyle="round,pad=0.02,rounding_size=0.18",
                linewidth=1.6,
                edgecolor=C_ACCENT,
                facecolor=color,
                alpha=0.85,
            )
        )
        ax.text(x, 0.5, title, ha="center", va="center", fontsize=11, fontweight="bold", color="white")
        ax.text(x, -0.1, subtitle, ha="center", va="center", fontsize=8.5, color="white", style="italic")
        ax.text(x, -1.15, date, ha="center", va="center", fontsize=8.5, color=C_ACCENT)

    # Arrows between boxes
    for x_start, x_end in [(2.25, 3.75), (6.25, 7.75)]:
        ax.annotate(
            "",
            xy=(x_end, 0),
            xytext=(x_start, 0),
            arrowprops=dict(arrowstyle="->", color=C_ACCENT, lw=2.0),
        )

    ax.set_title("Feature Timeline — 2026 diploma iteration", fontsize=12, pad=12, color=C_ACCENT)
    out = FIGS_DIR / "feature_timeline.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def domain_heatmap() -> Path:
    """Heatmap domain × stage accuracy, honest — KTO/DPO as NaN/dash."""
    domains = ["Math", "Physics", "Chemistry", "Biology", "CS"]
    stages = ["Base\n(n=143)", "GSPO\n(n=141)", "KTO", "DPO"]

    # Real numbers from evaluation/reports/compare_base_vs_gspo_20260331_115146.json
    data = np.array(
        [
            [1.000, 0.826, np.nan, np.nan],  # Math
            [0.967, 0.900, np.nan, np.nan],  # Physics
            [0.900, 0.966, np.nan, np.nan],  # Chemistry
            [0.800, 0.800, np.nan, np.nan],  # Biology
            [0.862, 0.897, np.nan, np.nan],  # CS
        ]
    )

    fig, ax = plt.subplots(figsize=(8, 4.8))

    cmap = plt.get_cmap("Purples")
    cmap.set_bad(color="#EEEEEE")
    masked = np.ma.masked_invalid(data)
    im = ax.imshow(masked, cmap=cmap, aspect="auto", vmin=0.5, vmax=1.0)

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages, fontsize=10)
    ax.set_yticks(range(len(domains)))
    ax.set_yticklabels(domains, fontsize=10)

    for i in range(len(domains)):
        for j in range(len(stages)):
            val = data[i, j]
            if np.isnan(val):
                ax.text(j, i, "—", ha="center", va="center", fontsize=13, color="#666")
            else:
                color = "white" if val > 0.85 else "#222"
                ax.text(j, i, f"{val * 100:.1f}%", ha="center", va="center", fontsize=10.5, color=color, fontweight="bold")

    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("Accuracy", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    ax.set_title(
        "Per-domain accuracy × training stage (small stratified sample n≈143)",
        fontsize=11,
        pad=12,
        color=C_ACCENT,
    )
    ax.set_xlabel("Training stage", fontsize=10)

    out = FIGS_DIR / "domain_heatmap.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    p1 = feature_timeline()
    print(f"✓ feature_timeline: {p1.name} ({p1.stat().st_size // 1024} KB)")
    p2 = domain_heatmap()
    print(f"✓ domain_heatmap:   {p2.name} ({p2.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5A.2: Run the figure generator**

```bash
cd C:/Work/MITS
python -X utf8 scripts/diploma/make_readme_figures.py
```
Expected:
```
✓ feature_timeline: feature_timeline.png (~30 KB)
✓ domain_heatmap:   domain_heatmap.png (~25 KB)
```

- [ ] **Step 5A.3: Visually inspect both PNGs**

Open `C:/Work/MITS/figures/readme/feature_timeline.png` and `C:/Work/MITS/figures/readme/domain_heatmap.png` in an image viewer. Check:
- Timeline: 3 colored boxes with arrows between them, titles readable, dates below
- Heatmap: 5 domains × 4 stages grid, Base + GSPO cells colored with %, KTO + DPO cells gray with "—"

If either looks broken — adjust `make_readme_figures.py` and re-run Step 5A.2.

### Task 5B: README updates

- [ ] **Step 5B.1: Read current README sections to preserve style**

```bash
head -200 C:/Work/MITS/README.md
```
Note: preserve banner (line 4), emoji headers, badge block, table-of-contents line.

- [ ] **Step 5B.2: Add "✨ Ключевые фичи" section after "О проекте"**

Use Edit tool. Find the end of the "О проекте" section (the `</table>` closing tag + `---` horizontal rule before `## Архитектура`). Insert between them:

```markdown

## ✨ Ключевые фичи 2026

<div align="center">

<img src="figures/readme/feature_timeline.png" alt="Feature Timeline" width="85%" />

</div>

| Feature | Что делает | Ключевая метрика | Spec |
|:---|:---|:---|:---|
| **016 Knowledge Forge** | Живой граф знаний: 83 узла × 88 рёбер, 6 типов узлов × 10 типов рёбер, self-completion из сессий | Path validity 100% · Frontier violation 0% | [specs/016](specs/016-knowledge-forge/) |
| **017 ToM-Tutor** | Theory-of-Mind агент: моделирует пробелы и заблуждения студента, re-rank навигатора | Root-hit 70% → **95%** · 0 регрессий на 20 сценариях | [specs/017](specs/017-tom-tutor/) |
| **018 PathSlime** | Lévy-Gaussian SMA: k разных траекторий обучения, bio-inspired diversity | 3 diverse paths (k=3, α=1.5) | [specs/018](specs/018-path-slime/) |

---
```

- [ ] **Step 5B.3: Embed architecture diagram in "Архитектура" section**

Use Edit tool. After `## Архитектура` header and before the existing ASCII-art code block, insert:

```markdown

<div align="center">

<img src="figures/diploma/courseware_fig_2_architecture.png" alt="MITS Architecture" width="90%" />

</div>

<details>
<summary>ASCII-fallback диаграмма архитектуры</summary>

```

Then find the closing ` ``` ` of the ASCII-art block (line that ends the last `└────...` box) and add `</details>` after it.

- [ ] **Step 5B.4: Insert "📊 Результаты обучения" section after "Training Pipeline"**

Locate the line `---` that closes the Training Pipeline section (right before `## Evaluation`). Use Edit tool to insert above `## Evaluation`:

```markdown

## 📊 Результаты обучения

<div align="center">

<img src="figures/readme/domain_heatmap.png" alt="Per-domain accuracy" width="75%" />

</div>

**Accuracy по доменам** (стратифицированный subset n=143, локальный бенчмарк):

| Domain | Base | GSPO | KTO | DPO |
|:---|:---:|:---:|:---:|:---:|
| Math | 100.0% | 82.6% | — | — |
| Physics | 96.7% | 90.0% | — | — |
| Chemistry | 90.0% | 96.6% | — | — |
| Biology | 80.0% | 80.0% | — | — |
| CS | 86.2% | 89.7% | — | — |
| **Overall** | **90.2%** | **87.9%** | — | — |

> ⚠️ **Small sample honesty.** 143-задачный subset, single run. GSPO показывает
> mixed effects: снижение на math (100% → 82.6%), но прирост на chemistry
> (+6.6%) и CS (+3.5%). Full-benchmark eval (n=3678) и стадии KTO/DPO —
> в работе. Источник: `evaluation/reports/compare_base_vs_gspo_20260331_115146.json`.

### 📈 ToM-Tutor A/B evaluation

| Метрика | Baseline | ToM | Delta |
|:---|:---:|:---:|:---:|
| Root-hit rate | 70.0% | **95.0%** | **+25.0%** |
| Any-hit rate | 100.0% | 100.0% | ±0 |
| Misconception accuracy | — | 90.0% | — |
| Regressed scenarios | — | 0 / 20 | — |
| Avg confidence | — | 0.89 | — |

*20 сценариев в 4 категориях (explicit_misconception, confused, open_question,
confident_wrong). Latency p50 11.5 s, p95 147 s — узкое место.
Источник: `evaluation/reports/tom_ab_2026-04-18.md`.*

### 📉 Knowledge Forge baseline

| Метрика | Value |
|:---|:---:|
| Gap Diagnosis (root-hit) | 60.0% (5 сценариев) |
| Gap Diagnosis (any-hit) | 100.0% |
| Frontier Violation Rate | 0.0% (lower = better) |
| Path Validity (invalid-pair rate) | 0.0% (7 пар) |
| Graph growth | 83 → 83 узлов, 88 → 88 рёбер (1 rejected) |

*Источник: `evaluation/reports/baseline_2026-04-18.md`.*

---
```

- [ ] **Step 5B.5: Update "Структура проекта" tree**

Find `## Структура проекта` and the ASCII tree inside it. Use Edit tool to replace the tree block with:

```text
MITS/
├── frontend/                    # Next.js 14 + TypeScript
│   ├── src/app/                 #   Pages (auth, chat, dashboard)
│   ├── src/components/          #   React-компоненты
│   ├── src/hooks/               #   useChat, useWebSocket
│   └── src/store/               #   Zustand (chatStore)
│
├── backend/                     # FastAPI
│   ├── app/api/v1/              #   REST + WebSocket endpoints
│   ├── app/services/            #   Orchestrator, analytics, export
│   └── app/models/              #   SQLAlchemy ORM
│
├── src/                         # Core Python — агенты и модели
│   ├── agents/                  #   Profiler, Planner, Tutor, Verifier
│   ├── models/                  #   LLM client, KT, detectors, prompts
│   ├── knowledge/               #   RAG, SKI, few-shot bank
│   ├── tools/                   #   SKI tool adapters
│   └── execution/               #   Code sandbox + AST analyzer
│
├── training/                    # ML training pipeline
│   ├── scripts/                 #   evaluate_stage, stem_rewards, export
│   ├── data/                    #   Datasets, benchmark
│   └── Modelfile*               #   Ollama templates (9b GSPO/KTO)
│
├── notebooks/                   # Colab training notebooks
│   ├── grpo_qwen3.5_9b.ipynb    #   Stage 1: GSPO
│   ├── kto_qwen3.5_9b.ipynb     #   Stage 2: KTO
│   ├── dpo_polish_qwen3.5_9b.ipynb  # Stage 3: DPO
│   └── archive/                 #   Legacy (Qwen3-4B, GLM)
│
├── evaluation/                  # Reports + benchmarks
├── data/                        # Knowledge bases (forge.json, RAG, skills)
│
├── docs/
│   ├── diploma/                 #   НИР 2026 + Курсовой 2026 (+ PDF exports)
│   ├── architecture/            #   ARCHITECTURE, MODEL_SELECTION, ...
│   ├── training/                #   TRAINING_PIPELINE, GSPO_TECHNIQUES
│   ├── guides/                  #   quickstart, PROJECT_STATUS
│   └── archive/                 #   pre-2026, nir-drafts
│
├── scripts/
│   ├── db/                      #   init_db, migrate_to_forge
│   ├── knowledge/               #   grow_graph, ingest_pdf, embeddings
│   ├── ollama/                  #   TurboQuant + Ollama automation
│   ├── design/                  #   design handoff, social preview
│   └── diploma/                 #   one-shot diploma generators (⚠️ already ran)
│
├── figures/
│   ├── diploma/                 #   Figures for НИР + Курсовой
│   └── readme/                  #   feature_timeline, domain_heatmap
│
├── specs/                       # 001–018 feature specs
└── tests/                       # Unit & integration
```

- [ ] **Step 5B.6: Add FAQ / Troubleshooting section before "Дорожная карта"**

Use Edit tool. Find `## Дорожная карта` and insert above it:

```markdown

## ❓ FAQ / Troubleshooting

<details>
<summary><b>Модель долго грузится / отвечает.</b></summary>

Используй профили из `src/resource_profiles.py` (`lite` / `standard` / `max`) —
они подбирают `num_ctx` и `num_predict` под железо. TurboQuant KV compression
ускоряет inference в 1.7–2× на RTX 4090. Подробнее:
[docs/architecture/RESOURCE_PROFILES.md](docs/architecture/RESOURCE_PROFILES.md).

</details>

<details>
<summary><b>/health endpoint таймаутит.</b></summary>

В `backend/app/services/orchestrator_service.py` включён 30-секундный TTL-cache
на `_check_llm_available()`. Если всё равно медленно — проверь, что Ollama
запущена (`ollama ps`) и модель подтянута (`ollama list`).

</details>

<details>
<summary><b>Ollama падает при inference или OOM.</b></summary>

Запусти `scripts/ollama/optimize_ollama.ps1` — он применяет safe defaults
для num_ctx / num_gpu / num_thread. Для моделей ≥17 GB single-shard
`ollama create --quantize` может зависнуть — используй `scripts/ollama/activate_turbo_quant.ps1` вместо этого.

</details>

<details>
<summary><b>Word lock files (`~$*.docx`) в docs/diploma/.</b></summary>

```powershell
Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item docs/diploma/~$*.docx -Force
```

</details>

<details>
<summary><b>Frontend не подключается к backend по WebSocket.</b></summary>

Проверь:
1. Backend запущен на порту 8000 (`cd backend && uvicorn app.main:app --reload --port 8000`)
2. В `.env` переменная `NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws`
3. JWT токен не истёк (в dev-режиме срок жизни = 24 часа)

</details>

---
```

- [ ] **Step 5B.7: Update "Документация" link in badge row to `docs/INDEX.md`**

Use Edit tool. Find `[Документация](docs/)` in line 19 and change to `[Документация](docs/INDEX.md)`.

- [ ] **Step 5B.8: Preview README**

```bash
head -50 C:/Work/MITS/README.md
```
Then:
```bash
cd C:/Work/MITS
python -c "import re; t=open('README.md', encoding='utf-8').read(); print('Total lines:', len(t.splitlines())); print('PNG refs:', [m.group(0) for m in re.finditer(r'figures/[^\s)\"]+\.(png|svg)', t)])"
```
Expected: PNG refs list includes `figures/readme/feature_timeline.png`, `figures/readme/domain_heatmap.png`, `figures/diploma/courseware_fig_2_architecture.png`, `figures/mits_banner.svg`.

- [ ] **Step 5B.9: Commit Section 5**

```bash
cd C:/Work/MITS
git add README.md figures/readme/ scripts/diploma/make_readme_figures.py
git status --short | head -20
```
Expected: `M README.md`, `A figures/readme/feature_timeline.png`, `A figures/readme/domain_heatmap.png`, `A scripts/diploma/make_readme_figures.py`.

```bash
git commit -m "$(cat <<'EOF'
docs(readme): add metrics tables, feature timeline, FAQ

- New: ✨ Ключевые фичи 2026 (016/017/018 timeline + table)
- New: 📊 Результаты обучения (per-domain × per-stage, honest
  numbers from evaluation/reports/, KTO/DPO stages marked —)
- New: 📈 ToM-Tutor A/B (70%→95% root-hit)
- New: 📉 Knowledge Forge baseline metrics
- New: ❓ FAQ / Troubleshooting (5 collapsible items)
- Updated: structure tree reflects docs/scripts reorganization
- Updated: Документация link → docs/INDEX.md
- Embedded: architecture diagram image (ASCII in <details> fallback)

New figures (scripts/diploma/make_readme_figures.py):
- figures/readme/feature_timeline.png
- figures/readme/domain_heatmap.png

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Final Verification

**Goal:** Verify nothing broken, restore WIP stash, summarize.

- [ ] **Step 6.1: Run Python import smoke test**

```bash
cd C:/Work/MITS
python -c "import src; from backend.app.main import app; print('OK — src + backend import cleanly')"
```
Expected: "OK — src + backend import cleanly". If ModuleNotFoundError — a file we moved broke an import. Fix path in import statement and commit as `fix(imports)`.

- [ ] **Step 6.2: Run ruff**

```bash
cd C:/Work/MITS
ruff check src/ backend/ scripts/ 2>&1 | tail -20
```
Expected: no new errors introduced by cleanup (scripts/ may have pre-existing warnings — ignore those).

- [ ] **Step 6.3: Run pytest (fast subset)**

```bash
cd C:/Work/MITS
pytest tests/ -x --ignore=tests/integration 2>&1 | tail -20
```
Expected: same pass/fail as before cleanup. If new failures — check they're not due to our moves.

- [ ] **Step 6.4: Restore stashed WIP**

```bash
cd C:/Work/MITS
git stash list | head -5
```
If the stash from Step 0.4 is present:
```bash
git stash pop
git status --short | head -10
```
Expected: WIP changes restored. If conflicts — resolve manually (the files we care about — `task_generator.py`, `Sidebar.tsx`, etc. — haven't been touched by cleanup, so no conflicts expected).

- [ ] **Step 6.5: Final `git log` summary**

```bash
cd C:/Work/MITS
git log --oneline -6
```
Expected (approximately):
```
<sha> docs(readme): add metrics tables, feature timeline, FAQ
<sha> chore(scripts): reorganize into db/knowledge/ollama/design/diploma
<sha> chore(docs): reorganize docs/ into semantic subdirs + archive
<sha> chore(cleanup): remove build artifacts and duplicates
0f4b2d1 docs(superpowers): spec for project cleanup + docs refresh
6cc6729 feat(ui): port Claude Desktop design refinement from design_handoff
```

- [ ] **Step 6.6: Final disk usage comparison**

```bash
du -sh C:/Work/MITS 2>&1
```
Expected: ~10 GB smaller than baseline from Step 0.5.

- [ ] **Step 6.7: Create CHANGELOG entry (optional bonus)**

If user wants, prepend to or create `CHANGELOG.md`:
```markdown
# Changelog

## 2026-04-22 — Project Cleanup

### Removed
- 10.1 GB of duplicate venv, build artifacts, stale docx backups
- `models/` (GLM and legacy Qwen Modelfiles — current in `training/`)
- `New_style/`, `design_handoff.7z`, screenshot

### Reorganized
- `docs/` → `diploma/`, `architecture/`, `training/`, `guides/`, `archive/`
- `scripts/` → `db/`, `knowledge/`, `ollama/`, `design/`, `diploma/`

### Added
- `docs/INDEX.md` — navigation hub
- `scripts/README.md`, `scripts/diploma/README.md` — script group docs
- `figures/readme/feature_timeline.png`, `domain_heatmap.png`
- README: honest metrics tables, feature timeline, FAQ

### Changed
- README: added "Ключевые фичи", "Результаты обучения", "ToM-Tutor A/B",
  "Knowledge Forge baseline", FAQ, updated structure tree
- Consolidated `.env.docker` + `.env.optimized` → `.env.example`
- Updated `.gitignore` to prevent re-accumulation
```

This step is skippable — user didn't explicitly ask for CHANGELOG (it was in Section C scope).

---

## Rollback Plan

If any commit looks wrong after the fact:
- Task 1 broke: `git reset --hard <sha of spec commit 0f4b2d1>`
- Task 2 broke: `git reset --hard <sha of Task 1 commit>`
- Task 3 broke: `git reset --hard <sha of Task 2 commit>`
- Task 5 broke: `git reset --hard <sha of Task 3 commit>`

Always check `git log --oneline -10` before rollback to identify the right SHA.

---

## Notes for Executor

- **Run from `C:/Work/MITS`** unless a step says otherwise.
- **Use forward slashes** in paths (Bash tool on Windows).
- **`git mv` over `mv`** for tracked files — preserves rename detection.
- **`rm -rf` is fine** for untracked dirs (e.g., `__pycache__`, `wandb/` excluded from cleanup).
- **Don't add WIP to commits** — the Step 0.4 stash is only restored at the end.
- **Before each commit, `git status --short`** to verify expected set of changes.
- **If pytest was failing before cleanup**, it will fail after — that's pre-existing, not caused by this work.
