# DeepGuard AI — Vercel Deployment (Frontend)

## Prerequisites

- A [Vercel](https://vercel.com) account (free tier)
- GitHub repository connected to Vercel
- A deployed Cloud Run backend (see [`CLOUD_RUN.md`](CLOUD_RUN.md))

---

## GitHub Integration (Recommended)

1. Push your code to a GitHub repository
2. In the Vercel dashboard, click **Add New → Project** and import your repo
3. Vercel will auto-detect Vite. Verify these settings:

| Setting | Value |
|---------|-------|
| **Framework Preset** | Vite (auto-detected) |
| **Root Directory** | `frontend/` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |
| **Node Version** | 20.x or later |

4. Add the production environment variable:

| Name | Value |
|------|-------|
| `VITE_API_URL` | `https://deepguard-ai-xxxx.a.run.app` (your Cloud Run URL) |

5. Click **Deploy**. Vercel auto-deploys on every push to `main`.

> 💡 After deployment, update the Cloud Run `FRONTEND_URL` env var to match your Vercel domain so CORS is configured correctly.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes | Backend Cloud Run URL (e.g. `https://deepguard-ai-xxxx.a.run.app`) |

The frontend reads this at runtime via `import.meta.env.VITE_API_URL` (see [`frontend/src/utils/api.ts`](../frontend/src/utils/api.ts)). If unset, it falls back to `http://localhost:8000`.

### Preview Environment

Set a different `VITE_API_URL` for Preview deployments if you maintain a staging Cloud Run backend. In Vercel project **Settings → Environment Variables**, add the variable scoped to **Preview**.

---

## Monorepo Setup

The repository root contains both `backend/` and `frontend/` directories. In the Vercel project settings, set **Root Directory** to `frontend/`. Vercel will ignore the `backend/` directory and only build the frontend.

---

## Preview Deployments

Vercel automatically creates preview deployments for every pull request or branch push. Each preview gets a unique URL (`*.vercel.app`). This allows testing frontend changes against either:

- The **production** Cloud Run backend (set `VITE_API_URL` in Preview env)
- A **staging** Cloud Run backend (deploy a second service with `gcloud run deploy deepguard-ai-staging`)

Production and preview deployments coexist without interference.

---

## Production Checks

After deployment, confirm everything works:

```bash
# 1. Visit the Vercel URL — the UI should load without console errors
# 2. Open browser DevTools → Network tab
# 3. Upload an image — verify POST goes to the Cloud Run URL (not localhost)
# 4. Check CORS: response should include your Vercel domain in Access-Control-Allow-Origin
# 5. Run the verification script
python deployment/verify_deploy.py \
  --frontend https://your-app.vercel.app \
  --backend https://deepguard-ai-xxxx.a.run.app
```

Checklist for production readiness:

- [ ] `VITE_API_URL` set in Vercel project environment variables
- [ ] `FRONTEND_URL` set in Cloud Run environment variables (matches Vercel domain)
- [ ] CORS allows your Vercel domain (check `/api/analyze` response headers)
- [ ] File upload (image/video) completes end-to-end
- [ ] Analysis results display correctly
- [ ] PDF/Markdown report download works

---

## Custom Domain (Optional)

1. In Vercel project → **Settings** → **Domains**, add your custom domain
2. Follow Vercel's DNS configuration instructions (CNAME or nameservers)
3. Update `FRONTEND_URL` in Cloud Run env vars to match your custom domain
4. Verify: `curl -I https://your-custom-domain.com`
