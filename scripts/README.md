# MITS Scripts

Utility scripts for the MITS project, grouped by purpose.

## Subdirectories

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
**Already ran.** These scripts modified `docs/diploma/*.docx` and generated
`figures/diploma/*.png`. Kept for reproducibility. See `diploma/README.md` for details.

### `migrations/` — raw SQL migration files
Applied by db/init_db.py --extended. Also used by Alembic for schema baseline.

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
