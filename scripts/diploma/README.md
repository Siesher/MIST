# Diploma — One-shot Scripts

These scripts generated/modified the diploma documents (`docs/diploma/*.docx`)
and their figures in `figures/diploma/`. They ran once; their effect is
captured in the tracked `.docx` files.

**Do not re-run** unless you want to regenerate from scratch. Running them
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
