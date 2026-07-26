# DeepGuard AI — Command Reference

All commands documented here are verified against the current repository at `D:\adk-workspace\deepguard-ai\`.

---

## Backend

### Install dependencies

```
uv sync
```

Run from the project root. Installs all Python dependencies declared in `pyproject.toml` into the project virtual environment (`.venv/`). Use this whenever you pull new changes that update dependencies or when setting up the project for the first time.

### Start development server

```
uv run uvicorn app.api:app --reload --port 8000
```

Run from `backend/`. Starts the FastAPI application with hot-reload enabled so the server restarts on file changes. Listens on `http://localhost:8000`. Use this for local development.

### Start production server

```
uv run uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Run from `backend/`. Starts the FastAPI application without hot-reload, bound to all network interfaces. Use this inside a container or when deploying to a VM.

---

## Frontend

### Install dependencies

```
npm install
```

Run from `frontend/`. Installs all Node.js dependencies declared in `package.json`. Run this before starting the dev server or building.

### Start dev server

```
npm run dev
```

Run from `frontend/`. Starts the Vite development server (default `http://localhost:3000`). Use this for local frontend development.

### Build for production

```
npm run build
```

Run from `frontend/`. Produces an optimized production build in `frontend/dist/`.

### Preview production build

```
npm run preview
```

Run from `frontend/`. Serves the built output from `frontend/dist/` locally so you can verify the production build before deploying.

---

## Health Checks

All health endpoints are defined in `backend/app/api.py` and return a simple JSON response. Use these to verify the backend is running.

```
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

```
curl http://localhost:8000/livez
```

Expected: `{"status":"ok"}`

```
curl http://localhost:8000/health/ready
```

Expected: `{"status":"ready"}`

```
curl http://localhost:8000/readyz
```

Expected: `{"status":"ready"}`

---

## API Testing

```
curl -X POST http://localhost:8000/api/analyze -F "file=@/path/to/image.jpg"
```

Uploads an image file to the `/api/analyze` endpoint (defined in `backend/app/api.py:147`). Returns a JSON response with moderation analysis results. Replace `/path/to/image.jpg` with the actual path to an image file.

---

## Running Tests

### Unit tests

```
uv run pytest tests/ -v
```

Run from `backend/`. Discovers and runs all tests under `backend/tests/` with verbose output. Use frequently during development to catch regressions.

### Specific test files

```
uv run pytest tests/test_pipeline.py tests/test_sightengine_parser.py -v
```

Run from `backend/`. Limits execution to the listed test files. Useful when iterating on a specific module.

### E2E tests

```
uv run pytest tests/e2e/ -v
```

Run from `backend/`. Runs end-to-end tests that hit external APIs (SightEngine, Groq, etc.). Requires valid credentials in `.env`. Use before cutting a release.

### Frontend E2E tests (Playwright)

```
cd frontend && npx playwright test --config=playwright.config.ts
```

Run from the project root. Requires Playwright browsers to be installed (`npx playwright install`). Tests the frontend against the running dev or preview server.

---

## Evaluation Suite

Evaluation scripts live in `backend/tests/eval/run_evaluation.py`. They send test images to a running backend and write results to a report file.

### Dry run (list files without making requests)

```
uv run python tests/eval/run_evaluation.py --dry-run
```

Run from `backend/`. Prints which test images would be sent and what output file would be written, without actually making any HTTP requests. Use this to verify your dataset configuration.

### Full evaluation (requires running backend)

```
uv run python tests/eval/run_evaluation.py --url http://localhost:8000
```

Run from `backend/`. Sends each image in `eval_dataset/` to the specified backend URL and writes a results report to `eval_dataset/results.md`. Use this to benchmark model accuracy.

### Custom output file

```
uv run python tests/eval/run_evaluation.py --url http://localhost:8000 --output /path/to/custom.md
```

Run from `backend/`. Same as above but writes the report to a custom path instead of the default.

---

## Docker

### Build image

```
docker build -t deepguard-ai .
```

Run from the project root. Builds a production Docker image using the `Dockerfile` at the repository root.

### Run container

```
docker run -p 8000:8000 --env-file .env deepguard-ai
```

Maps host port 8000 to container port 8000 and loads environment variables from `.env`. Use this to test the containerized app locally.

### Stop container

```
docker stop <container-id>
```

Gracefully stops a running container. Get the container ID from `docker ps`.

### View logs

```
docker logs <container-id>
```

Prints stdout/stderr from the container. Add `-f` to follow logs live.

---

## Git Workflow

### Clone

```
git clone <repo-url>
```

Clones the repository to your local machine.

### Create branch

```
git checkout -b feature/your-feature-name
```

Creates and switches to a new feature branch. Use this pattern for all development work.

### Check status

```
git status
```

Shows working tree status — staged, unstaged, and untracked files.

### Pull latest

```
git pull origin main
```

Fetches and merges the latest changes from the remote `main` branch. Do this before creating a new branch.

### View diff

```
git diff
```

Shows unstaged changes in the working tree.

### Review staged changes

```
git diff --cached
```

Shows changes that are staged for the next commit.

---

## Verification Script

The verification script at `deployment/verify_deploy.py` performs end-to-end smoke tests against a deployed backend (and optionally a frontend).

### Test deployment

```
python deployment/verify_deploy.py --backend https://your-backend.a.run.app
```

Run from the project root. Hits health endpoints and runs a sample API call against the deployed backend. Use this after deploying to Cloud Run.

### Test frontend + backend

```
python deployment/verify_deploy.py --backend https://your-backend.a.run.app --frontend https://your-app.vercel.app
```

Run from the project root. Also checks that the frontend loads and that CORS between frontend and backend is correctly configured.

---

## Environment Setup

### Copy example env

```
cp .env.example .env
```

Run from the project root. Creates `.env` from the template. Edit this file with your API keys before starting the backend.

### Edit .env with your API keys

Add values for:

| Variable | Required for |
|---|---|
| `SIGHTENGINE_API_USER` | Image moderation via SightEngine |
| `SIGHTENGINE_API_SECRET` | Image moderation via SightEngine |
| `GROQ_API_KEY` | LLM-powered analysis via Groq |
| `PRIMARY_API_KEY` | API authentication (required by backend) |
| `GOOGLE_API_KEY` | Gemini model access (optional fallback) |
