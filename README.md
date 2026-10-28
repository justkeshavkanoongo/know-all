# Know It All

Know It All is a thoughtful learning platform beginning with a focused catalog of five subjects. This milestone includes a responsive course-discovery site and a small typed API that serves its course outline data.

## Repository structure

- `apps/web/` — Next.js App Router, React, TypeScript and Tailwind CSS.
- `apps/api/` — FastAPI app, Pydantic response models, reviewed in-memory learning content, PostgreSQL quest/evidence/artifact persistence, Alembic migrations and API tests.
- `package.json` / `pnpm-workspace.yaml` — root workspace scripts and frontend workspace membership.
- `.venv/` — local Python environment; ignored by Git.

The API is the single source of truth for course, reviewed lesson and practice content. Quest identities, sessions, invitations, pair membership, independently checked preparation evidence, and shared artifact revisions use PostgreSQL. Learning content remains version-controlled; browser-local progress remains local and untrusted. German and French show representative CEFR A1–C2 levels; their outlines do not claim that complete lessons have been authored.

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

For local quests, PostgreSQL 18 is required. The ignored `apps/api/.env` file holds the development URLs and a stable local session secret. The API does not load it automatically; the documented shell workflow sources it into the API process. The placeholder-only template is `apps/api/.env.example`. See [the Phase 5 contract](docs/m5-quest-contract.md) for details.

## Run locally

Start the API in one terminal from the repository root:

```bash
source .venv/bin/activate
if [ ! -e apps/api/.env ]; then
  python3 - <<'PY'
from pathlib import Path
import secrets
path = Path('apps/api/.env')
text = Path('apps/api/.env.example').read_text()
text = text.replace('QUEST_SESSION_SECRET=replace-with-at-least-32-random-bytes', f'QUEST_SESSION_SECRET={secrets.token_urlsafe(48)}')
with path.open('x') as file:
    file.write(text)
PY
fi
set -a
source apps/api/.env
set +a
pnpm db:upgrade
pnpm api:dev
```

The creation block runs only if `apps/api/.env` does not exist and uses exclusive file creation, so it cannot overwrite an existing local environment file. It generates the secret without printing it. Keep this file unchanged across API restarts so redemption retries remain deterministic. `pnpm api:dev` checks that PostgreSQL is reachable, the migration head is current, and the session secret is configured before binding port 8000; it exits with a safe setup message if any prerequisite is missing.

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
- `GET /api/quests/{quest_id}/preparation` → per-member distinct checked evidence and preparation status.
- `POST /api/quests/{quest_id}/preparation/check` → reuses the reviewed server-side practice checker and stores only correct, membership-bound evidence. Each participant must answer all seven distinct exercises correctly.
- `GET /api/quests/{quest_id}/artifact` → current four-section snapshot and up to 50 latest immutable revisions.
- `PATCH /api/quests/{quest_id}/artifact/sections/{section_id}` → appends a complete snapshot using the expected revision and an idempotency key; stale writes return 409 with `current_revision`.
- An unknown course slug returns HTTP 404 with `{ "code": "course_not_found", "message": "..." }`.

When both quest members independently complete the seven reviewed practice exercises, one transaction moves the quest from `preparing` to `collaborating` and creates its initial empty artifact revision. Artifact edits preserve the full snapshot, derive authorship from the guest session, and use database revision constraints and row locks. Artifact text is returned as data and rendered as text. Preparation evidence verifies answers for a pseudonymous quest session; it does not prove two distinct people, identity, age, or formal mastery. Cancellation and expiry defaults remain subject to product policy.

The reviewed German A1 assessment bank currently contains exactly 15 distinct questions, enough for one attempt. A new attempt or retake returns HTTP 409 `assessment_bank_exhausted` until another full set of reviewed questions is authored; questions are never silently repeated or generated.

Learning progress is stored in this browser under the versioned key `know-it-all:progress:v2`. Practice outcomes follow normal API-checked submissions, and assessment receipts pass client consistency checks before entering the progress reducer; the browser does not submit scores or XP. A lesson is marked complete after a full checked practice set or a submitted assessment. Mastery requires at least five distinct checked answers for a concept and at least 80% accuracy. XP is derived from an idempotent reward ledger; levels advance every 50 XP. Local data is user-editable, not account-backed, synced, tamper-proof, or authoritative for social, payment, or access decisions. Existing v1 progress and corrupt/future data are preserved and shown as unsupported until an explicit reset; no migration is performed.

Course IDs and slugs are stable identifiers. The course catalog and reviewed learning content live in memory/version control in `apps/api/app`; PostgreSQL persists guest identities/sessions, quests, participants, invitation hashes, idempotency metadata, independently checked preparation evidence, and artifact snapshots/revisions.

## Tests and production checks

From the repository root with `.venv` activated:

```bash
pnpm test:api
export TEST_DATABASE_URL='postgresql+psycopg://koham@127.0.0.1:5432/know_it_all_test'
export DATABASE_URL="$TEST_DATABASE_URL"
pnpm db:upgrade
pnpm test:api:integration
pnpm test:progress
pnpm typecheck
pnpm build:web
```

`pnpm test:api` covers the API and learning flows. `pnpm test:api:integration` runs real PostgreSQL tests for guest sessions, invitation concurrency, independent preparation, artifact revisions, rollback, and persistence across an API process restart. Point both URLs to the isolated `know_it_all_test` database and apply migrations before running it; the fixture refuses other database names and deletes only rows created by each test. `pnpm test:progress` exercises progress validation, storage version handling, mastery, XP, achievement and idempotency rules using Node's built-in test runner. `pnpm typecheck` checks the TypeScript application. `pnpm build:web` creates the Next.js production build.

## Design and scope

The provisional Warm Editorial palette uses warm off-white, white surfaces, navy, ink, muted sage, and quiet borders. Typography uses local system font stacks so the app does not depend on a remote font service. The layout adapts from one column on small screens to multiple course columns on wide screens, with visible focus styles and semantic headings and navigation.

Account authentication, AI/RAG, peer feedback, quest mastery checks/rewards, OpenClaw and deployment are out of scope. Guest sessions are pseudonymous with adult self-attestation only. The local PostgreSQL `koham` role is currently a superuser; use a dedicated least-privilege role before shared/public use. Progress and existing XP remain limited to the reviewed German A1 lesson and current browser profile; local XP is not server-authoritative or merged with Quest preparation evidence.
