# Evaluation Harness

This folder contains the offline architecture and quality evaluation harness.

## Run

```bash
PYTHONPATH=src python3 evals/run_architecture_eval.py --clean
```

Outputs are written to `eval_outputs/architecture_eval_latest/`:

- `architecture_eval_report.html`
- `summary_metrics.csv`
- `run_metrics.csv`
- `lead_metrics.csv`
- `claim_metrics.csv`
- `confusion_matrix.csv`
- `summary.json`

`eval_outputs/architecture_eval_history.csv` is appended on every run so regressions can be tracked over time.

## What This Eval Measures

- run completion vs `waiting_for_input`
- prompt country / industry / offer / source-plan extraction
- stage/ledger completeness
- artifact reference integrity
- lead artifact coverage
- tool-path compliance
- lead status accuracy
- minimum per-class recall
- zero-recall class collapse
- predicted class coverage
- false-qualified guard
- public evidence gate
- claim-level evidence support

## Current Limitation

The bundled benchmark is synthetic. That is useful for structural regression, but it is not enough to prove real-world lead quality.

The next eval tier should add a manually labeled real corpus with:

- raw prompt
- discovered company
- crawled page text
- source URLs
- expected lead status
- expected rejection/manual-review reason
- human usefulness label
- eventual outreach outcome when available

Until that corpus exists, `real_corpus_presence` intentionally fails as a production-readiness gate.
