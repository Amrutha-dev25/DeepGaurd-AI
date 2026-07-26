# DeepGuard AI — Evaluation Dataset

## Structure

```
eval_dataset/
├── images/
│   ├── real/          # Ground-truth authentic photographs
│   └── fake/          # Ground-truth AI-generated or manipulated images
├── videos/
│   ├── real/          # Ground-truth authentic videos
│   └── fake/          # Ground-truth AI-generated or manipulated videos
└── README.md
```

## Ground Truth Convention

The **folder name** IS the ground truth:
- Files placed in `images/real/` are expected to be classified as **real** (authentic).
- Files placed in `images/fake/` are expected to be classified as **fake** (AI-generated or manipulated).
- Same convention for `videos/real/` and `videos/fake/`.

The evaluation script (`backend/tests/eval/run_evaluation.py`) walks these folders,
sends each file through the live `/api/analyze` pipeline, and compares the verdict
against the folder name to compute accuracy metrics.

## Supported Extensions

| Type | Extensions |
|------|------------|
| Images | `.jpg`, `.jpeg`, `.png`, `.webp` |
| Videos | `.mp4`, `.webm`, `.mov`, `.avi` |

Files with unsupported extensions are skipped with a warning.

## Limitations

See [`KNOWN_LIMITATIONS.md`](../KNOWN_LIMITATIONS.md) for details on known evaluation accuracy constraints:

- **Sightengine quota**: Free tier (~500 req/day). When exhausted, fallback LLM models are measurably less accurate.
- **Video accuracy**: Current video accuracy is ~30% — key frame extraction and detection consistency need improvement.
- **Groq token limits**: Router and Report agents fall back when daily token quota (100k TPD) is exhausted.

These limitations affect **evaluation accuracy**, not system stability. The pipeline always completes.

## Notes

- Actual media files are **not** committed to the repository (see `.gitignore` rules).
- The `.gitkeep` files preserve the folder structure in version control.
- For best results, use diverse, real-world samples — not synthetic test fixtures.
- Run `python backend/tests/eval/run_evaluation.py --url <backend-url>` to execute.
- Results are written to `results.md` in this directory.
