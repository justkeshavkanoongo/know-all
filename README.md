# Know It All

Know It All is a thoughtful learning platform beginning with a focused catalog of five subjects. This milestone includes a responsive course-discovery site and a small typed API that serves its course outline data.

## Repository structure

- `apps/web/` — Next.js App Router, React, TypeScript and Tailwind CSS.
- `apps/api/` — FastAPI app, Pydantic response models, in-memory catalog and API tests.
- `package.json` / `pnpm-workspace.yaml` — root workspace scripts and frontend workspace membership.
- `.venv/` — local Python environment; ignored by Git.

The API is the single source of truth for course content. The frontend fetches summaries for the catalog and detail responses for each course page. German and French show representative CEFR A1–C2 levels; their outlines do not claim that complete lessons have been authored.

## Prerequisites

- Node.js 26.x
- pnpm 12.15.0
- Python 3.12

## Install dependencies

From the repository root:

```bash
pnpm install

# Create this only when .venv does not already exist.
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r apps/api/requirements.txt
```

The frontend and backend dependencies are declared separately in `apps/web/package.json` and `apps/api/requirements.txt`. Direct frontend dependencies are pinned exactly; `pnpm install` resolves and records the full dependency tree in the root `pnpm-lock.yaml`. The Python requirements pin the backend and test dependencies exactly.

## Run locally

Start the API in one terminal from the repository root:

```bash
source .venv/bin/activate
pnpm api:dev
```

The API listens at `http://127.0.0.1:8000`. Its interactive schema is at `http://127.0.0.1:8000/docs`.

Start the frontend in a second terminal:

```bash
pnpm dev:web
```

Open `http://localhost:3000`. The server-rendered frontend reads `API_BASE_URL`; it defaults to `http://127.0.0.1:8000`. To use another local API address, copy `apps/web/.env.example` to `apps/web/.env.local` and change that value. Do not put credentials in frontend environment files.

## API contract

- `GET /health` → `{ "status": "ok", "service": "know-all-api" }`
- `GET /api/courses` → typed summaries for exactly German, French, Literature, Psychology and Philosophy.
- `GET /api/courses/{slug}` → a typed detail with learning rationale, representative curriculum note, levels and modules.
- An unknown course slug returns HTTP 404 with `{ "code": "course_not_found", "message": "..." }`.

Course IDs and slugs are stable identifiers. The catalog currently lives in memory in `apps/api/app/catalog.py`; there is no database in this milestone.

## Tests and production checks

From the repository root with `.venv` activated:

```bash
pnpm test:api
pnpm typecheck
pnpm build:web
```

`pnpm test:api` covers health, the exact five-course catalog, each course detail and the unknown-slug error. `pnpm typecheck` checks the TypeScript application. `pnpm build:web` creates the Next.js production build.

## Design and scope

The provisional Warm Editorial palette uses warm off-white, white surfaces, navy, ink, muted sage, and quiet borders. Typography uses local system font stacks so the app does not depend on a remote font service. The layout adapts from one column on small screens to multiple course columns on wide screens, with visible focus styles and semantic headings and navigation.

Authentication, databases, AI, RAG, quizzes, gamification, social features, OpenClaw and deployment are intentionally outside this milestone.
