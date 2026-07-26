# `tests/` — Backend Test Suite

Unit tests, integration tests, and evaluation infrastructure for DeepGuard AI.

## Layout

```
tests/
├── __init__.py
├── test_pipeline.py             # 47 unit tests (forensics, guardrails, agents, config, services)
├── test_sightengine_parser.py   # 7 parser schema tests (Sightengine response parsing)
├── gen_test_image.py            # Test image generator utility
├── test_diag.png                # Generated test image
├── test_video.mp4               # Test video sample
├── e2e/                         # Live-API tests (requires real API keys)
│   ├── conftest.py
│   ├── test_real_image_api.py
│   └── test_real_video_api.py
├── e2e_verify_all.py            # Offline pipeline verification (no API calls)
├── run_e2e_tests.ps1            # PowerShell E2E test runner
├── eval/                        # Evaluation suite
│   ├── run_evaluation.py        # Walk eval_dataset, POST each file, compare verdicts
│   ├── run_with_server.py       # Test utility for starting server + running tests
│   ├── verify_steps.py          # Step-by-step verification
│   └── verify_results.json      # Expected results fixture
└── test_*.py                    # Various unit/integration tests
```

## Running Tests

```bash
# From backend/
uv run pytest tests/ -v                        # All unit tests
uv run pytest tests/test_pipeline.py -v        # Pipeline tests only
uv run pytest tests/test_sightengine_parser.py -v  # Parser tests only
uv run pytest tests/e2e/ -v                    # E2E tests (requires .env keys)
```

## Evaluation Suite

The `eval/` subdirectory contains tools for running the full evaluation dataset:

```bash
# Dry run (list files without API calls)
uv run python tests/eval/run_evaluation.py --dry-run

# Full evaluation (requires running backend)
uv run python tests/eval/run_evaluation.py --url http://localhost:8000
```

See [`eval_dataset/README.md`](../eval_dataset/README.md) for dataset details.

## Writing Tests

- Place unit tests at `tests/test_*.py`
- Place integration tests in `tests/integration/`
- Place E2E tests in `tests/e2e/`
- Use pytest fixtures from `tests/e2e/conftest.py` for live-server tests
- Test data lives in `tests/` directory (test_diag.png, test_video.mp4)
