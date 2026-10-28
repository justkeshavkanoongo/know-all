# Phase 5, Increment 1 — Guest Quest Contract

Increment 1 provides pseudonymous guest sessions, creation of a pair-only German A1 quest, one-use invitations, and membership-protected quest reads. Increment 2 adds independently checked preparation and one shared, revisioned learning artifact. Neither increment adds accounts, AI, peer feedback, mastery checks, or Quest XP.

## Local PostgreSQL setup

The API uses SQLAlchemy 2 with Psycopg 3 (`postgresql+psycopg://`) and Alembic. Schema changes are versioned under `apps/api/migrations/versions`. Database URLs are read from process environment; `.env` files are not loaded by the application. The README's startup block creates `apps/api/.env` only when it is absent, generates the session secret without printing it, and then sources the file into the shell. Do not replace or overwrite an existing local environment file or commit it.

```sh
# If needed, create apps/api/.env with the README's exclusive first-run block.
set -a
source apps/api/.env
set +a
pg_isready -h 127.0.0.1 -p 5432
pnpm db:upgrade
pnpm api:dev
```

The examples target `know_it_all_dev` and `know_it_all_test`; migrations only create/update versioned application tables and never drop or reset an existing database. Use the configured application role only for local development. The current local `koham` role is a PostgreSQL superuser; before any shared or production use, create a dedicated least-privilege role limited to the application databases and required schema operations.

To run real database integration tests, configure both URLs to the isolated test database, migrate it, then run the separately marked suite:

```sh
export DATABASE_URL='postgresql+psycopg://koham@127.0.0.1:5432/know_it_all_test'
export TEST_DATABASE_URL="$DATABASE_URL"
pnpm db:upgrade
pnpm test:api:integration
```

The integration fixture refuses a URL whose database name is not exactly `know_it_all_test`; it does not drop tables or truncate data. It uses UUID-scoped rows and removes only rows created by each test. Stop the API with Ctrl+C; stop a Homebrew-managed local database only when desired using `brew services stop postgresql@18`.

## Data and authorization

- Identities are random pseudonymous IDs. The adult-only pilot uses a server-recorded 18+ self-attestation; it does not verify identity or age and a guest ID does not prove a distinct human.
- Session tokens are high-entropy opaque values issued only as `HttpOnly; SameSite=Lax` cookies (also `Secure` when `ENVIRONMENT=production` or `NODE_ENV=production`). PostgreSQL stores SHA-256 token hashes only. Rotation leaves the prior session valid for at most two minutes to reduce concurrent-request races. Session expiry is 30 days.
- Cookie-authenticated mutations require an exact configured `Origin` (`WEB_ORIGIN`, default `http://localhost:3000`). The same-origin Next.js proxy forwards cookie, origin, idempotency key, and upstream `Set-Cookie` headers without exposing the cookie token to browser JavaScript.
- Quest creation accepts only lesson `german-a1-greetings`, concept `german-greetings`, and template `concept-guide-v1`. Host membership is derived from the validated session. New quests start `awaiting_partner`; successful redemption transitions to `preparing`; both participants completing all seven distinct reviewed practice exercises transitions to `collaborating`.
- The host is the only participant who can issue or revoke an invitation. Quest reads and mutations require membership; unknown and non-member quest IDs both return 404.
- Invitations contain a 48-byte random URL-safe token; only its SHA-256 hash is stored. They are single-use, expire after a provisional 72-hour default (bounded by quest expiry), and may be revoked/reissued by the host. Anyone who possesses an unused link may claim it before expiry or revocation.
- Redemption locks the invitation and quest rows in PostgreSQL. A database trigger and service transaction enforce a maximum of two members; unique keys prevent duplicate membership and duplicate hosts. The collaborator identity, session, membership, state transition, and invitation redemption commit together.
- The redemption endpoint accepts `Idempotency-Key`. On a retry with the same key within two minutes, it deterministically reissues the same session cookie using `QUEST_SESSION_SECRET`; the secret is not stored in the database. Retrying with a different key after redemption gets the generic unavailable response.
- `QUEST_TTL_DAYS` defaults to 30 days. Invitation and inactivity expiry durations, quest withdrawal/cancellation policy, data retention/deletion/export/reporting, and launch privacy/legal review still require product policy approval. These TTLs are provisional implementation defaults, not settled policy.
- There is no production-grade rate limiter. Add one before a public pilot. Local in-memory throttling is intentionally not presented as cross-worker protection.

## Endpoints

All domain errors use `{ "code": "stable_code", "message": "safe summary" }`. FastAPI schema errors remain 422. Session-required returns 401; disallowed origin returns 403; non-member/unknown quest and unusable invitation return generic 404; idempotency or state conflicts return 409; missing database/session-secret configuration returns safe 503. Validation errors do not include secrets.

| Method/path | Contract |
|---|---|
| `POST /api/guest-sessions` | Body `{ "confirm_adult": true }`; returns `{ identity_id, expires_at }`, sets HttpOnly cookie. A valid existing browser cookie preserves the identity. |
| `POST /api/guest-sessions/rotate` | Cookie + same-origin `Origin`; returns identity and expiry, sets replacement cookie. |
| `DELETE /api/guest-sessions/current` | Cookie + same-origin `Origin`; revokes the session and clears cookie; 204. |
| `POST /api/quests` | Cookie, `Origin`, and `Idempotency-Key`; body `{ "lesson_id":"german-a1-greetings", "concept_ids":["german-greetings"], "template_id":"concept-guide-v1" }`; returns `QuestResponse`. Reuse of a key with different request fingerprint is 409. |
| `GET /api/quests/{quest_id}` | Cookie + membership; returns `QuestResponse`; unknown/non-member is 404. |
| `POST /api/quests/{quest_id}/invitations` | Host cookie, `Origin`, and `Idempotency-Key`; returns `{ invitation_token, expires_at, status }`. The raw token is returned once and never stored. Repeating that operation key returns `invitation_token: null`; use a fresh key to rotate/reissue. |
| `DELETE /api/quests/{quest_id}/invitations` | Host cookie + `Origin`; revokes current unused link; 204. |
| `POST /api/quest-invitations/redeem` | `Origin`, `Idempotency-Key`, body `{ "token":"…", "confirm_adult":true }`; atomically adds one collaborator, creates a session cookie, transitions quest to `preparing`, and returns `QuestResponse`. Invalid, expired, revoked, already-used, or full quests share a generic 404. |

`QuestResponse` contains `quest_id`, state, fixed lesson/concept/template IDs, participant count, allowed actions, creation/expiry timestamps, and version. It includes no participant profile data. `QuestCreate`, `GuestSessionCreate`, and `InvitationRedeem` reject unknown fields and constrain identifiers to the approved initial content.

## Increment 2 — independently checked preparation and shared artifact

### Preparation

`GET /api/quests/{quest_id}/preparation` returns `PreparationStatus` with `quest_id`, `current_role`, state, and per-role `checked_count`, `required_count: 7`, stable checked `evidence_ids`, and `complete`.

`POST /api/quests/{quest_id}/preparation/check` accepts the existing strict `PracticeCheckRequest` shape, for example `{ "exercise_id":"german-a1-greeting-time", "answer":"option-a" }`. It reuses the existing reviewed practice bank and canonical `check_practice_answer` implementation. Correct answers insert evidence keyed by `(quest_id, session-derived identity_id, evidence_id)`; incorrect attempts return deterministic feedback and create no qualifying evidence. Replaying a correct answer cannot increase the distinct evidence count. Client-reported correctness, evidence definitions, and participant IDs are not accepted. Preparation requires all seven distinct exercises for each membership; when the second member qualifies, one transaction advances the quest and creates artifact revision 0.

Preparation evidence is bound to a pseudonymous session-derived membership and checked against server-controlled answers. Guest sessions remain self-issued: this is not proof of two distinct people, identity, age, or formal mastery. Browser-local progress is not used.

### Artifact

The initial artifact has four typed sections: `explanation`, `example`, `misconception_correction` (`misconception` plus `correction`), and `follow_up_question`. Text limits are 2,000 characters for explanation/example, 1,200 per misconception/correction value, 1,000 for follow-up, and 5,000 total. Empty initial revision 0 is system-authored. Accepted edits require non-empty content and create a full immutable snapshot; authorship and role are derived from the authenticated membership. The database rejects revision updates and direct deletes (quest cascade cleanup remains allowed), uses unique `(artifact_id, revision_number)`, and ties the current revision pointer to an existing revision.

`GET /api/quests/{quest_id}/artifact` returns the current snapshot, revision number, up to the latest 50 revision snapshots with server-derived `author_role` and `changed_section`, and `history_truncated`.

`PATCH /api/quests/{quest_id}/artifact/sections/{section_id}` requires `Idempotency-Key` and accepts `{ "expected_revision": 0, "content": "A concise explanation." }`. For `misconception_correction`, `content` is `{ "misconception":"...", "correction":"..." }`. A successful response is the accepted `ArtifactRevisionResponse`. Exact retries with the same key and payload return that revision; reusing the key with another payload returns 409 `idempotency_key_reused`. A stale expected revision returns 409 `{ "code":"artifact_revision_conflict", "message":"...", "current_revision":N }`; clients refresh the full snapshot before reconciling. The API locks the quest/artifact, inserts the revision, advances the pointer, and commits atomically. PostgreSQL constraints and the deferred current-revision foreign key prevent dangling or duplicate revisions. A failed transaction rolls back all associated changes.

Quest state remains `preparing` until both are ready, then `collaborating`; existing cancellation and expiry rules are otherwise unchanged. Expiry remains derived at read time for active states using the existing provisional TTL. The artifact requires membership and `collaborating` state on every read and write. Both role labels must appear as authors in accepted revisions before the UI reports both participants contributed. No presence, realtime transport, peer feedback, completion state, mastery, or Quest XP is added.

### Increment 2 endpoints

| Method/path | Behavior |
|---|---|
| `GET /api/quests/{quest_id}/preparation` | Member-only preparation status; role-based labels only, no identities. |
| `POST /api/quests/{quest_id}/preparation/check` | Same-origin, member-only server-side check and idempotent correct evidence insert. |
| `GET /api/quests/{quest_id}/artifact` | Member-only current artifact and bounded revision history; only in collaboration. |
| `PATCH /api/quests/{quest_id}/artifact/sections/{section_id}` | Same-origin member edit; strict section/content validation, expected revision and idempotency key. |

All quest routes return the existing generic 404 for unknown and non-member quest IDs. Request-schema errors are FastAPI 422 responses; semantically invalid section content returns flat 400 `invalid_artifact_section`. Stale revision and state conflicts are 409; stale artifact errors include `current_revision`. Database failures remain safe 503 responses and do not report a successful save.

The invitation UI puts its bearer token in the URL fragment, clears browser history immediately on load, and exchanges it only in a POST body. Fragments are not sent in HTTP requests or ordinary referrers. A bearer invitation is still claimable by whoever receives it first; do not forward it publicly.

## Integrity and deferred work

PostgreSQL transactions and unique constraints—not mocks—are used for duplicate/retry and concurrent invitation redemption, preparation evidence, and artifact revision tests. The API records guests, quest membership, checked preparation evidence, and artifact revisions durably, while Phase 4 browser-local progress/XP remains user-editable and non-authoritative. This increment issues no Quest XP. There is no authentication account, cross-device recovery, chat persistence, contribution moderation, session/device inventory, production threat review, or production role provisioning yet.
