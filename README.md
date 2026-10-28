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
- `GET /api/lessons/{lesson_id}` → a typed, reviewed lesson detail. The initial lesson is `german-a1-greetings`; unknown IDs return HTTP 404 with `{ "code": "lesson_not_found", "message": "..." }`.
- `GET /api/lessons/{lesson_id}/practice` → reviewed public exercises for that lesson, without answer keys.
- `POST /api/lessons/{lesson_id}/practice/check` → deterministic answer checking for multiple choice, matching and fill in the blank. The browser reaches these endpoints through same-origin Next.js proxy routes.
- `POST /api/lessons/{lesson_id}/assessment-attempts` → create a 15-question immutable attempt without exposing answer keys.
- `POST /api/lessons/{lesson_id}/assessment-attempts/{attempt_id}/submit` → server-side deterministic scoring, concept-level feedback and post-submit answer review. Results are idempotent for the same normalized answers; changed answers return 409.
- An unknown course slug returns HTTP 404 with `{ "code": "course_not_found", "message": "..." }`.

The reviewed German A1 assessment bank currently contains exactly 15 distinct questions, enough for one attempt. A new attempt or retake returns HTTP 409 `assessment_bank_exhausted` until another full set of reviewed questions is authored; questions are never silently repeated or generated.

Learning progress is stored in this browser under the versioned key `know-it-all:progress:v2`. Practice outcomes follow normal API-checked submissions, and assessment receipts pass client consistency checks before entering the progress reducer; the browser does not submit scores or XP. A lesson is marked complete after a full checked practice set or a submitted assessment. Mastery requires at least five distinct checked answers for a concept and at least 80% accuracy. XP is derived from an idempotent reward ledger; levels advance every 50 XP. Local data is user-editable, not account-backed, synced, tamper-proof, or authoritative for social, payment, or access decisions. Existing v1 progress and corrupt/future data are preserved and shown as unsupported until an explicit reset; no migration is performed.

Course IDs and slugs are stable identifiers. The catalog currently lives in memory in `apps/api/app/catalog.py`; there is no database in this milestone.

## Tests and production checks

From the repository root with `.venv` activated:

```bash
pnpm test:api
pnpm test:progress
pnpm typecheck
pnpm build:web
```

`pnpm test:api` covers the API and learning flows. `pnpm test:progress` exercises progress validation, storage version handling, mastery, XP, achievement and idempotency rules using Node's built-in test runner. `pnpm typecheck` checks the TypeScript application. `pnpm build:web` creates the Next.js production build.

## Design and scope

The provisional Warm Editorial palette uses warm off-white, white surfaces, navy, ink, muted sage, and quiet borders. Typography uses local system font stacks so the app does not depend on a remote font service. The layout adapts from one column on small screens to multiple course columns on wide screens, with visible focus styles and semantic headings and navigation.

Authentication, databases, AI tutoring, RAG, social features, OpenClaw and deployment are intentionally out of scope. Progress and rewards are limited to the reviewed German A1 lesson and exist only in the current browser profile.
