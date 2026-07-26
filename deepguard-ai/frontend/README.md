# DeepGuard AI — Frontend

The frontend is a **React 19** single-page application built with **Vite**, **TypeScript**, and **Tailwind CSS**. It provides the user interface for uploading images/videos, viewing forensic analysis results, and exploring interactive overlays.

---

## Folder Layout

```
frontend/
├── src/
│   ├── components/
│   │   ├── Header.tsx              # App bar with logo & nav
│   │   ├── Footer.tsx              # Footer with links
│   │   ├── UploadZone.tsx          # Drag-and-drop file upload
│   │   ├── InteractiveViewer.tsx   # Zoomable viewer with anomaly overlays
│   │   ├── LoggerPane.tsx          # Real-time pipeline log panel
│   │   ├── ReportPane.tsx          # Formatted analysis report display
│   │   └── SpaceBackgroundGrid.tsx # Animated background effect
│   ├── utils/
│   │   └── api.ts                  # Backend API client (fetch wrapper)
│   ├── data/
│   │   └── samples.ts              # Static demo exhibits
│   ├── types.ts                    # TypeScript type definitions
│   ├── App.tsx                     # Root app component
│   ├── main.tsx                    # React entry point
│   └── index.css                   # Tailwind imports + global styles
├── tests/
│   └── e2e/                        # Playwright end-to-end tests
├── index.html                      # Vite HTML entry
├── vite.config.ts                  # Vite configuration (dev proxy, build)
├── tsconfig.json                   # TypeScript config
├── playwright.config.ts            # Playwright test config
├── package.json                    # Dependencies & scripts
├── .env.example                    # Dev environment variables
└── .env.production.example         # Production environment variables
```

---

## Key Files

| File | Purpose |
|---|---|
| `src/utils/api.ts` | API client — detects `VITE_API_URL` (prod) or `VITE_API_BASE` (dev), falls back to `http://localhost:8000`. Sends `POST /api/analyze` with file data, parses the response into typed frontend models. |
| `src/types.ts` | All TypeScript interfaces: `SampleMedia`, `AnalysisOverlay`, `BackendAnalysisResponse`, etc. |
| `src/data/samples.ts` | Pre-built static exhibits for demo mode (no backend needed). |
| `src/App.tsx` | Root component — owns app state, routes upload → analysis → report flow. |

---

## Setup & Run

```powershell
cd frontend
npm install
npm run dev          # starts on http://localhost:3000
```

The dev server proxies API requests to `localhost:8000` by default. To use a different backend URL, set `VITE_API_BASE` in a `.env` file.

---

## Build for Production

```powershell
npm run build        # outputs to dist/
npm run preview      # preview the production build locally
```

---

## Environment Variables

| Variable | Used In | Default | Description |
|---|---|---|---|
| `VITE_API_BASE` | development | `http://localhost:8000` | Backend URL for `npm run dev` |
| `VITE_API_URL` | production | — | Backend URL for production build (overrides `VITE_API_BASE`) |

Create a `.env` file in the `frontend/` directory (copy from `.env.example`). The API client checks `VITE_API_URL` first, then `VITE_API_BASE`, then falls back to `localhost:8000`.

```env
VITE_API_BASE=http://localhost:8000
```

---

## How It Connects to the Backend

1. User drops a file onto `UploadZone`
2. `App.tsx` calls `analyzeMedia(file)` from `api.ts`
3. `api.ts` sends a `POST /api/analyze` request with `FormData` (multipart file upload) to the backend
4. Backend runs the full pipeline, returns a `BackendAnalysisResponse` JSON body
5. `api.ts` transforms the response into a `SampleMedia` object (typed in `types.ts`)
6. App renders `InteractiveViewer` (visual overlays), `ReportPane` (text report), and `LoggerPane` (pipeline log)

> **Demo mode**: If no backend is running, the app can use static exhibits from `data/samples.ts` for UI development and demonstrations.

---

## Component Overview

| Component | Role |
|---|---|
| `UploadZone` | Drag-and-drop area, file type validation, upload progress |
| `InteractiveViewer` | Canvas-based zoomable viewer, renders anomaly bounding boxes from `AnalysisOverlay[]` |
| `ReportPane` | Verdict badge (Real/Fake/Inconclusive), confidence score, risk level, findings list, recommendations |
| `LoggerPane` | Scrollable log of pipeline steps (fed from backend `diagnostic_images` / audit trail) |
| `Header` | App branding, optional nav links |
| `Footer` | Copyright, version info |
| `SpaceBackgroundGrid` | Decorative animated grid background |

---

## Extension Points

| What | How |
|---|---|
| **Add a new component** | Create `src/components/NewThing.tsx`, import in `App.tsx` |
| **Support a new media type** | Update `api.ts` mapping and `types.ts` interfaces |
| **Add a new demo sample** | Edit `src/data/samples.ts` — add an entry with sample URL, verdict, findings |
| **Customize styling** | Edit `src/index.css` (Tailwind directives) or use Tailwind utility classes |
| **Add E2E tests** | Create `tests/e2e/new-test.spec.ts` following Playwright conventions |
| **Add new visualization** | Build on `InteractiveViewer` — add overlay types, tooltips, or heatmap layers |
