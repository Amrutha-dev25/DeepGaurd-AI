# DeepGuard AI — Cloud Run Deployment (Backend)

## Prerequisites

- [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated
- A Google Cloud project with billing enabled
- Required APIs enabled:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com
```

---

## Option A: One-Shot Deploy (Cloud Build from Source)

Builds the container directly from source and deploys in one step.

```bash
export PROJECT_ID="your-gcp-project"
export REGION="us-central1"
export SERVICE_NAME="deepguard-ai"

gcloud builds submit \
  --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE_NAME}"

gcloud run deploy ${SERVICE_NAME} \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE_NAME}" \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --port 8000 \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 4 \
  --timeout 120 \
  --memory 2Gi \
  --cpu 2 \
  --startup-cpu-boost \
  --set-env-vars "^&^FRONTEND_URL=https://your-app.vercel.app&LOG_LEVEL=info&ENABLE_GEMINI_FALLBACK=true" \
  --update-secrets=SIGHTENGINE_API_USER=SIGHTENGINE_API_USER:latest,SIGHTENGINE_API_SECRET=SIGHTENGINE_API_SECRET:latest,GROQ_API_KEY=GROQ_API_KEY:latest,PRIMARY_API_KEY=PRIMARY_API_KEY:latest,GOOGLE_API_KEY=GOOGLE_API_KEY:latest,TAVILY_API_KEY=TAVILY_API_KEY:latest
```

> ⚠️ The `^&^` prefix in `--set-env-vars` changes the delimiter to `&` so values can contain commas. If using `--update-secrets`, create Secret Manager secrets first (see below).

---

## Option B: Two-Step Build & Deploy (CI/CD)

Preferred for automated pipelines — separates build from deployment.

```bash
# 1. Create Artifact Registry repository (one-time)
gcloud artifacts repositories create deepguard-ai \
  --repository-format docker \
  --location ${REGION}

# 2. Build and push
gcloud builds submit \
  --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/deepguard-ai/backend:$(git rev-parse --short HEAD)"

# 3. Deploy
gcloud run deploy deepguard-ai \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/deepguard-ai/backend:$(git rev-parse --short HEAD)" \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --port 8000 \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 4 \
  --timeout 120 \
  --memory 2Gi \
  --cpu 2 \
  --startup-cpu-boost
```

> 💡 This is the pattern used by the [GitHub Actions workflow](../.github/workflows/deploy.yml).

### GitHub Actions CI/CD

The repository includes a pre-configured workflow (`.github/workflows/deploy.yml`) that:
1. Authenticates with Google Cloud via a service account key (`GCP_SA_KEY` secret)
2. Builds and pushes to Artifact Registry
3. Deploys to Cloud Run with env vars from secrets/vars
4. Runs post-deploy health verification

Required secrets/vars:
| Name | Type | Description |
|------|------|-------------|
| `GCP_SA_KEY` | Secret | Service account JSON key |
| `GCP_PROJECT_ID` | Variable | GCP project ID |
| `GCP_REGION` | Variable | GCP region (e.g. `us-central1`) |
| `FRONTEND_URL` | Variable | Vercel frontend URL |

---

## Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SIGHTENGINE_API_USER` 🔒 | Yes | Sightengine API username |
| `SIGHTENGINE_API_SECRET` 🔒 | Yes | Sightengine API secret |
| `GROQ_API_KEY` 🔒 | Yes | Groq API key (Router + Report primary) |
| `PRIMARY_API_KEY` 🔒 | Yes | NVIDIA NIM API key (analysis fallback) |
| `GOOGLE_API_KEY` 🔒 | Conditional | Gemini API key (if `ENABLE_GEMINI_FALLBACK=true`) |
| `FRONTEND_URL` | Yes | Vercel frontend URL (for CORS) |
| `ENABLE_GEMINI_FALLBACK` | No | Set `true` to enable Gemini fallback tier |
| `TAVILY_API_KEY` 🔒 | No | Web search tool key |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING` (default: `INFO`) |
| `MAX_RETRIES_PRIMARY` | No | Retry count before fallback (default: `2`) |
| `REQUEST_TIMEOUT_SECONDS` | No | Per-request timeout (default: `240`) |
| `MAX_FILE_SIZE_MB` | No | Upload limit in MB (default: `100`) |
| `CORS_ORIGINS` | No | Extra CORS origins (comma-separated) |
| `RATE_LIMIT_PER_MINUTE` | No | Max requests per minute (default: `20`) |
| `PII_REDACTION_ENABLED` | No | PII redaction (default: `true`) |
| `INJECTION_DETECTION_ENABLED` | No | Injection detection (default: `true`) |

### Using Secret Manager

For production, use `--update-secrets` instead of `--set-env-vars` for sensitive values:

```bash
# Create secrets (one-time)
gcloud secrets create SIGHTENGINE_API_USER --replication-policy automatic
echo -n "your_user" | gcloud secrets versions add SIGHTENGINE_API_USER --data-file=-

gcloud secrets create SIGHTENGINE_API_SECRET --replication-policy automatic
echo -n "your_secret" | gcloud secrets versions add SIGHTENGINE_API_SECRET --data-file=-

# Grant the Cloud Run service account access
gcloud secrets add-iam-policy-binding SIGHTENGINE_API_USER \
  --member "serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role "roles/secretmanager.secretAccessor"

# Deploy with secrets
gcloud run deploy ${SERVICE_NAME} \
  --image ... \
  --update-secrets=SIGHTENGINE_API_USER=SIGHTENGINE_API_USER:latest,SIGHTENGINE_API_SECRET=SIGHTENGINE_API_SECRET:latest
```

---

## Health Check Probes

Cloud Run uses HTTP probes against the container. The Dockerfile includes a `HEALTHCHECK` instruction as well.

| Endpoint | Cloud Run Mapping | Purpose |
|----------|-------------------|---------|
| `GET /health` | Startup / Liveness | Container is alive and accepting traffic |
| `GET /livez` | Liveness (alias) | Same as `/health` |
| `GET /health/ready` | Readiness | Container is ready to serve |
| `GET /readyz` | Readiness (alias) | Same as `/health/ready` |

No special Cloud Run probe configuration is required — these are automatically available.

---

## Verification

```bash
# Get the Cloud Run URL
SERVICE_URL=$(gcloud run services describe deepguard-ai \
  --region us-central1 \
  --format 'value(status.url)')

# Health check
curl -sf ${SERVICE_URL}/health && echo "OK"
# → {"status":"ok"}

# Readiness check
curl -sf ${SERVICE_URL}/readyz && echo "OK"
# → {"status":"ready"}

# API analyze (requires a test image)
curl -sf -X POST ${SERVICE_URL}/api/analyze \
  -F "file=@test_image.jpg" | jq .verdict

# Full deployment verification
python deployment/verify_deploy.py --backend ${SERVICE_URL}
```

---

## Rollback

```bash
# List recent revisions
gcloud run revisions list --service deepguard-ai --region us-central1

# Route 100% of traffic to a previous revision
gcloud run services update-traffic deepguard-ai \
  --region us-central1 \
  --to-revisions=DEEPGUARD-AI-<REVISION_NAME>=100
```

---

## Logs & Monitoring

```bash
# Tail live logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=deepguard-ai"

# Query recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=deepguard-ai" \
  --limit 50 --format json | jq '.[].textPayload'

# Open Cloud Run dashboard
echo "https://console.cloud.google.com/run/detail/us-central1/deepguard-ai/logs"
```

### Key Metrics

| Metric | Expected Value | Notes |
|--------|---------------|-------|
| Request latency | 25–60s | Depends on file size + provider response time |
| Container startup | ~2–3s | Cold start (scale from zero) |
| Memory usage | 1.2–1.5 GiB | OpenCV preprocessing peak |
| Concurrent requests | 4 max | Hard limit via `--concurrency` |

---

## Scaling Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `--min-instances` | `0` | Scale to zero when idle (free tier eligible) |
| `--max-instances` | `1` | Prevents runaway costs; increase if concurrent demand grows |
| `--concurrency` | `4` | Each request uses ~1–2 CPU during inference |
| `--timeout` | `120s` | Cloud Run max request duration. Analysis takes 25–60s; 2× buffer |
| `--memory` | `2Gi` | OpenCV + ADK agents need 1.2–1.5 GiB |
| `--cpu` | `2` | Multi-threaded image preprocessing benefits from 2 vCPUs |
| `--startup-cpu-boost` | enabled | Speeds cold start for the first request after scale-from-zero |

> 💡 The app-level `REQUEST_TIMEOUT_SECONDS` (default `240`) is intentionally higher than Cloud Run's `120s` timeout. This ensures the app waits for a provider response rather than timing out internally before Cloud Run cuts the connection.

---

## Troubleshooting

### Cold Starts

- **Symptom:** First request after idle takes >5s
- **Cause:** Cloud Run scales to zero; container starts fresh
- **Fix:** Set `--min-instances 1` to keep one instance warm (incurs cost). `--startup-cpu-boost` is already enabled to minimize startup time.
- **Expected cold start:** ~2–3s

### Memory (OOM Kills)

- **Symptom:** Container exits with code `137` or `OutOfMemoryError` in logs
- **Cause:** OpenCV video processing with large files spikes memory beyond 2 GiB
- **Fix:** Reduce `VIDEO_MAX_FRAMES` or `IMAGE_TARGET_SIZE` in env. Or increase `--memory 4Gi`.

### Timeouts

- **Symptom:** `504 Deadline Exceeded` from Cloud Run
- **Cause:** Analysis pipeline exceeds the `120s` Cloud Run timeout
- **Diagnosis:** Check if `REQUEST_TIMEOUT_SECONDS` is set too high (>120). Cloud Run will terminate the request before the app does.
- **Fix:** Reduce `REQUEST_TIMEOUT_SECONDS` to `110` or increase Cloud Run `--timeout`. The eval script uses `300s` — this is separate and only applies locally.

### Provider Failures

- **Symptom:** `fallback_triggered: true` in responses
- **Cause:** Sightengine, Groq, or NVIDIA API errors / rate limits
- **Fix:** Check API key validity in Cloud Run env vars or Secret Manager. Verify provider status dashboards.

---

## Terraform (Optional)

Terraform templates in `deployment/terraform/` provide Infrastructure-as-Code for the full GCP setup (Cloud Run, storage, telemetry, IAM). They are **not required** for deployment and remain unchanged.
