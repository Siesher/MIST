"""Add per-stage incremental save + resume capability to Cell 9.

Per user request (Вариант 3): bulletproof against Colab disconnect.
Each stage saved immediately к disk + Drive после completion. На старте
Cell 9 чекает существующие per-stage files и skip'ает.

New flow:
  1. mkdir evaluation/reports/honest_phase0a_YYYYMMDD/ (repo) + Drive mirror
  2. For each stage: skip if {stage}.json exists; otherwise run + save individually
  3. After all stages: assemble final merged report (как раньше)

Recovery scenario:
  - Disconnect мid-gspo (base done, gspo half-way)
  - Resume: re-run Cell 9 → base loaded from disk, gspo re-runs from scratch,
    kto runs after.
  - Total wasted compute: only the partial stage at disconnect time.
"""
import json
from pathlib import Path

NB = Path('notebooks/honest_eval_full_precision.ipynb')
nb = json.loads(NB.read_text(encoding='utf-8'))


def get_src(cell):
    s = cell.get('source', '')
    return s if isinstance(s, list) else s.splitlines(keepends=True)


# Find the run cell (Cell 9, last code cell with 'Run Phase 0a')
target_idx = None
for i, c in enumerate(nb['cells']):
    src = ''.join(get_src(c))
    if 'Run Phase 0a' in src and 'eval_stage(stage_name' in src:
        target_idx = i
        break
assert target_idx is not None, 'Could not find Phase 0a run cell'
print(f'Found run cell at index {target_idx}')

NEW_CELL_SRC = '''# Cell 9: Run Phase 0a with per-stage incremental save (resumable).
# Каждый stage saved immediately после completion → disconnect-resilient.
# Resume: re-run эту cell — completed stages loaded from disk, остальные re-run.
date_tag = datetime.utcnow().strftime('%Y%m%d')
stage_dir = PROJECT_ROOT / f'evaluation/reports/honest_phase0a_{date_tag}'
stage_dir.mkdir(parents=True, exist_ok=True)
drive_root = Path('/content/drive/MyDrive/MITS_secrets')
drive_stage_dir = drive_root / f'honest_phase0a_{date_tag}' if drive_root.exists() else None
if drive_stage_dir is not None:
    drive_stage_dir.mkdir(parents=True, exist_ok=True)

logger.info(f'Per-stage save dir (repo): {stage_dir}')
if drive_stage_dir:
    logger.info(f'Per-stage save dir (Drive): {drive_stage_dir}')

results = {}
for stage_name, adapter_id in ADAPTERS.items():
    stage_file = stage_dir / f'{stage_name}.json'
    drive_stage_file = (drive_stage_dir / f'{stage_name}.json') if drive_stage_dir else None

    # Resume: skip if already saved on disk (или Drive — restore оттуда)
    if stage_file.exists():
        logger.info(f'[RESUME] {stage_name} already saved at {stage_file}, loading')
        results[stage_name] = json.loads(stage_file.read_text(encoding='utf-8'))
        continue
    if drive_stage_file is not None and drive_stage_file.exists():
        logger.info(f'[RESUME from Drive] {stage_name} loading from {drive_stage_file}')
        results[stage_name] = json.loads(drive_stage_file.read_text(encoding='utf-8'))
        # Mirror back к repo for git-tracked artifact
        stage_file.write_text(drive_stage_file.read_text(encoding='utf-8'), encoding='utf-8')
        continue

    logger.info(f'>>> Starting stage: {stage_name}')
    r = eval_stage(stage_name, adapter_id, calc_problems, fast_mode=True)
    results[stage_name] = r

    # Save IMMEDIATELY — repo + Drive
    stage_file.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f'[SAVED] {stage_file} ({stage_file.stat().st_size / 1024:.1f} KB)')
    if drive_stage_file is not None:
        drive_stage_file.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f'[SAVED Drive] {drive_stage_file}')

# All stages complete — assemble final merged report
report = {
    'protocol': 'honest_full_precision_phase0a',
    'mode': 'fast_programmatic',
    'note': (
        'Phase 0a: accuracy via programmatic numeric/string match (extract_answer vs '
        'ground_truth, 2% tolerance). Per-stage incremental save в stage_dir. '
        'socratic_score / leak_rate deferred to Phase 0b (async Cerebras judge).'
    ),
    'timestamp': datetime.utcnow().isoformat(),
    'decoding_config': {k: v for k, v in DECODING_CONFIG.items() if k != 'system_prompt'},
    'system_prompt_hash': hash(DECODING_CONFIG['system_prompt']),
    'n_problems': len(calc_problems),
    'base': {k: v for k, v in results['base'].items() if k != 'completions'},
    'gspo': {k: v for k, v in results['gspo'].items() if k != 'completions'},
    'kto':  {k: v for k, v in results['kto'].items()  if k != 'completions'},
    'completions': {stage: r['completions'] for stage, r in results.items()},
}

out_repo  = PROJECT_ROOT / f'evaluation/reports/honest_full_precision_phase0a_{date_tag}.json'
out_drive = drive_root / f'honest_full_precision_phase0a_{date_tag}.json' if drive_root.exists() else None
out_repo.parent.mkdir(parents=True, exist_ok=True)
out_repo.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
logger.info(f'Saved merged report (repo): {out_repo}')
if out_drive:
    out_drive.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f'Saved merged report (Drive): {out_drive}')

print('\\n=== Phase 0a — Honest accuracy (full-precision bf16, identical decoding, programmatic correctness) ===')
for stage in ['base', 'gspo', 'kto']:
    r = results[stage]
    print(f"{stage:5s}  acc={r['accuracy']:.3f} ({r['n_judged']}/{r['n']} judged) | "
          f"acc_non_trunc={r['accuracy_non_truncated']:.3f} ({r['n_non_truncated']}/{r['n']}) | "
          f"trunc={r['truncation_rate']:.1%} | think_close={r['think_close_rate']:.1%}")
print('\\nNote: acc_non_trunc — accuracy ON completed answers только (excluded truncated).')
print('Note: socratic_score / leak_rate — Phase 0b (run scripts/score_phase0b_async.py later).')
'''

nb['cells'][target_idx]['source'] = NEW_CELL_SRC.splitlines(keepends=True)
print('Cell 9 rewritten with per-stage incremental save + resume')


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print()
print('Patch applied. New flow:')
print('  - Each stage saved as evaluation/reports/honest_phase0a_YYYYMMDD/{stage}.json')
print('  - Drive mirror: /content/drive/MyDrive/MITS_secrets/honest_phase0a_YYYYMMDD/')
print('  - On Cell 9 re-run: completed stages loaded from disk, only missing ones run')
print('  - Final merged report: evaluation/reports/honest_full_precision_phase0a_YYYYMMDD.json')
