# Training Pipeline

The `src/training` directory contains the anomaly detection training pipeline.

## Usage

Run training locally:
```bash
python src/training/train.py --force --output-dir artifacts
```

This will:
1. Load config from `src/training/config.yaml`.
2. Load data (or generate synthetic if missing).
3. Check for drift (unless `--force` is used).
4. Train Isolation Forest model.
5. Evaluate on test set.
6. Save artifacts to `artifacts/`.
7. Promote model to `src/anomaly/anomaly_if.pkl` if validation passes.

## Artifacts

Artifacts are saved in:
- `artifacts/models/`: Timestamped pickle files.
- `artifacts/pipelines/`: Timestamped preprocessing pipelines.
- `artifacts/metrics/`: JSON metrics including drift stats.
- `artifacts/logs/`: Training logs.

## Continuous Training

The pipeline runs automatically via GitHub Actions `.github/workflows/continuous-training.yml`.
It runs weekly or can be triggered manually via workflow dispatch.
