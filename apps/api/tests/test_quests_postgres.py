"""Real PostgreSQL quest/session integration coverage; no database mocks."""
from __future__ import annotations

import os
import hashlib
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.database import dispose_engine, get_engine
from app.main import app
from app.quest_tables import (
    GuestIdentity, GuestSession, Invitation, Quest, QuestArtifact,
    QuestArtifactRevision, QuestArtifactReview, QuestArtifactReviewResponse,
    QuestParticipant, QuestPreparationEvidence,
)
from app.quests import COOKIE_NAME

pytestmark = pytest.mark.postgres
ORIGIN = "http://localhost:3000"


@pytest.fixture(autouse=True)
def test_database(monkeypatch: pytest.MonkeyPatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL must point to the isolated know_it_all_test database")
    parsed = urlparse(url)
    if parsed.path.lstrip("/") != "know_it_all_test":
        pytest.fail("Refusing to run integration tests unless TEST_DATABASE_URL targets know_it_all_test")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("QUEST_SESSION_SECRET", "local-integration-test-secret-at-least-32-bytes")
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    dispose_engine()
    engine = get_engine()
    with engine.connect() as connection:
        version = connection.scalar(text("select current_setting('server_version_num')::int"))
        assert int(version) >= 120000
        assert connection.scalar(text("select to_regclass('public.alembic_version') is not null"))
    owned_identities: set[UUID] = set()
    owned_quests: set[UUID] = set()
    yield owned_identities, owned_quests
    with Session(engine) as session, session.begin():
        if owned_quests:
            joined_ids = session.scalars(select(QuestParticipant.identity_id).where(QuestParticipant.quest_id.in_(owned_quests)))
            redeemed_ids = session.scalars(select(Invitation.redeemed_by).where(
                Invitation.quest_id.in_(owned_quests), Invitation.redeemed_by.is_not(None)))
            owned_identities.update(joined_ids)
            owned_identities.update(redeemed_ids)
            session.execute(delete(Quest).where(Quest.id.in_(owned_quests)))
        if owned_identities:
            session.execute(delete(GuestIdentity).where(GuestIdentity.id.in_(owned_identities)))
    dispose_engine()


def guest(client: TestClient, owned: set[UUID]) -> UUID:
    response = client.post("/api/guest-sessions", json={"confirm_adult": True}, headers={"Origin": ORIGIN})
    assert response.status_code == 200, response.text
    identity = UUID(response.json()["identity_id"])
    owned.add(identity)
    assert COOKIE_NAME in response.headers.get("set-cookie", "")
    assert "httponly" in response.headers["set-cookie"].lower()
    return identity


def create_quest(client: TestClient, owned_quests: set[UUID], key: str = "quest-key-1") -> UUID:
    response = client.post("/api/quests", json={
        "lesson_id": "german-a1-greetings", "concept_ids": ["german-greetings"], "template_id": "concept-guide-v1"
    }, headers={"Origin": ORIGIN, "Idempotency-Key": key})
    assert response.status_code == 200, response.text
    quest_id = UUID(response.json()["quest_id"])
    owned_quests.add(quest_id)
    return quest_id


def test_guest_session_hash_rotation_revocation_and_invalid_token(test_database) -> None:
    identities, _ = test_database
    with TestClient(app) as client:
        identity_id = guest(client, identities)
        first_cookie = client.cookies.get(COOKIE_NAME)
        with Session(get_engine()) as db:
            stored = db.scalar(select(GuestSession).where(GuestSession.identity_id == identity_id))
            assert stored is not None and stored.token_hash != first_cookie
            assert len(stored.token_hash) == 64
        rotated = client.post("/api/guest-sessions/rotate", headers={"Origin": ORIGIN})
        assert rotated.status_code == 200
        rotated_cookie = client.cookies.get(COOKIE_NAME)
        assert client.get("/api/quests/00000000-0000-0000-0000-000000000001").status_code == 404
        assert client.cookies.get(COOKIE_NAME) != first_cookie
        assert client.delete("/api/guest-sessions/current", headers={"Origin": ORIGIN}).status_code == 204
        assert client.get("/api/quests/00000000-0000-0000-0000-000000000001").status_code == 401
        client.cookies.set(COOKIE_NAME, first_cookie)
        assert client.get("/api/quests/00000000-0000-0000-0000-000000000001").status_code == 401
        client.cookies.set(COOKIE_NAME, "invalid-session-token")
        assert client.get("/api/quests/00000000-0000-0000-0000-000000000001").status_code == 401

    with TestClient(app) as expired_client:
        expired_identity = guest(expired_client, identities)
        with Session(get_engine()) as db, db.begin():
            expired_session = db.scalar(select(GuestSession).where(GuestSession.identity_id == expired_identity))
            assert expired_session
            expired_session.expires_at = expired_session.created_at - timedelta(seconds=1)
        assert expired_client.get("/api/quests/00000000-0000-0000-0000-000000000001").status_code == 401


def test_create_idempotency_authorization_and_database_persistence(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as other:
        guest(host, identities)
        guest(other, identities)
        quest_id = create_quest(host, quest_ids)
        assert create_quest(host, quest_ids) == quest_id
        changed = host.post("/api/quests", json={"lesson_id": "german-a1-greetings", "concept_ids": ["german-greetings"], "template_id": "concept-guide-v1"}, headers={"Origin": ORIGIN, "Idempotency-Key": "quest-key-1"})
        assert changed.status_code == 200
        assert changed.json()["quest_id"] == str(quest_id)
        assert other.get(f"/api/quests/{quest_id}").status_code == 404
        assert host.get(f"/api/quests/{quest_id}").json()["participant_count"] == 1
        dispose_engine()  # Force a fresh connection pool, as after a worker restart.
        assert host.get(f"/api/quests/{quest_id}").status_code == 200


def test_invitation_is_single_use_atomic_and_retryable(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host:
        guest(host, identities)
        quest_id = create_quest(host, quest_ids)
        issued = host.post(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN, "Idempotency-Key": "invite-key"})
        assert issued.status_code == 200, issued.text
        token = issued.json()["invitation_token"]
        assert token
        repeated_issue = host.post(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN, "Idempotency-Key": "invite-key"})
        assert repeated_issue.status_code == 200
        assert repeated_issue.json()["invitation_token"] is None
        assert repeated_issue.json()["status"] == "already_issued"
        with Session(get_engine()) as db:
            stored = db.scalar(select(Invitation).where(Invitation.quest_id == quest_id))
            assert stored and stored.token_hash != token and len(stored.token_hash) == 64

        def redeem(key: str):
            with TestClient(app) as client:
                return client.post("/api/quest-invitations/redeem", json={"token": token, "confirm_adult": True}, headers={"Origin": ORIGIN, "Idempotency-Key": key})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(redeem, ["redeem-a", "redeem-b"]))
        assert sorted(response.status_code for response in responses) == [200, 404]
        winner = next(response for response in responses if response.status_code == 200)
        with Session(get_engine()) as db:
            joined_identity = db.scalar(select(GuestSession.identity_id).where(
                GuestSession.token_hash == hashlib.sha256(winner.cookies.get(COOKIE_NAME).encode()).hexdigest()))
            assert joined_identity
            identities.add(joined_identity)
        assert winner.json()["state"] == "preparing"
        retry = redeem(next(key for key, result in zip(["redeem-a", "redeem-b"], responses) if result.status_code == 200))
        assert retry.status_code == 200
        assert retry.cookies.get(COOKIE_NAME) == winner.cookies.get(COOKIE_NAME)
        with Session(get_engine()) as db:
            invite = db.scalar(select(Invitation).where(Invitation.quest_id == quest_id))
            participants = db.scalar(select(text("count(*)")).select_from(QuestParticipant.__table__).where(QuestParticipant.quest_id == quest_id))
            assert invite and invite.redeemed_at and participants == 2


def test_revoked_expired_and_non_host_invites_are_unavailable(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as non_host:
        guest(host, identities)
        guest(non_host, identities)
        quest_id = create_quest(host, quest_ids, "quest-key-2")
        assert non_host.post(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN, "Idempotency-Key": "nope"}).status_code == 404
        assert non_host.delete(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN}).status_code == 404
        issued = host.post(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN, "Idempotency-Key": "invite-key-2"}).json()
        token = issued["invitation_token"]
        replacement = host.post(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN, "Idempotency-Key": "invite-key-2b"}).json()
        assert replacement["invitation_token"] and replacement["invitation_token"] != token
        assert non_host.post("/api/quest-invitations/redeem", json={"token": token, "confirm_adult": True}, headers={"Origin": ORIGIN, "Idempotency-Key": "redeem-reissued"}).status_code == 404
        token = replacement["invitation_token"]
        assert host.delete(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN}).status_code == 204
        assert non_host.post("/api/quest-invitations/redeem", json={"token": token, "confirm_adult": True}, headers={"Origin": ORIGIN, "Idempotency-Key": "redeem-revoked"}).status_code == 404


def test_invalid_content_and_expired_invitation_are_rejected(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as joiner:
        guest(host, identities)
        guest(joiner, identities)
        invalid = host.post("/api/quests", json={"lesson_id": "unknown", "concept_ids": ["fake"], "template_id": "fake"}, headers={"Origin": ORIGIN, "Idempotency-Key": "bad-content"})
        assert invalid.status_code == 422
        quest_id = create_quest(host, quest_ids, "quest-key-expiry")
        issued = host.post(f"/api/quests/{quest_id}/invitations", headers={"Origin": ORIGIN, "Idempotency-Key": "invite-expiry"}).json()
        token = issued["invitation_token"]
        with Session(get_engine()) as db, db.begin():
            invite = db.scalar(select(Invitation).where(Invitation.quest_id == quest_id))
            assert invite
            invite.expires_at = invite.created_at - timedelta(seconds=1)
        expired = joiner.post("/api/quest-invitations/redeem", json={"token": token, "confirm_adult": True}, headers={"Origin": ORIGIN, "Idempotency-Key": "redeem-expired"})
        assert expired.status_code == 404


def test_participant_cap_is_enforced_by_postgres_and_rolls_back(test_database) -> None:
    _, _ = test_database
    identity_ids = [UUID(int=1001), UUID(int=1002), UUID(int=1003)]
    quest_id = UUID(int=2001)
    engine = get_engine()
    with pytest.raises(IntegrityError):
        with Session(engine) as db, db.begin():
            now = datetime.now(timezone.utc)
            for identity_id in identity_ids:
                db.add(GuestIdentity(id=identity_id, adult_confirmed_at=now, created_at=now))
            db.add(Quest(id=quest_id, state="awaiting_partner", lesson_id="german-a1-greetings", concept_ids=["german-greetings"], template_id="concept-guide-v1", created_at=now, expires_at=now.replace(year=now.year + 1), version=1))
            db.flush()
            for identity_id, role in zip(identity_ids, ["host", "collaborator", "collaborator"]):
                db.add(QuestParticipant(quest_id=quest_id, identity_id=identity_id, role=role))
                db.flush()
    with Session(engine) as db:
        assert db.get(Quest, quest_id) is None
        assert all(db.get(GuestIdentity, identity_id) is None for identity_id in identity_ids)


def test_quest_and_session_persist_across_real_api_process_restart(test_database) -> None:
    identities, quest_ids = test_database
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": "apps/api",
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "QUEST_SESSION_SECRET": "local-integration-test-secret-at-least-32-bytes",
        "WEB_ORIGIN": ORIGIN,
    }

    def start_server() -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", str(port)],
            cwd=os.getcwd(), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    process = start_server()
    session_cookie: str | None = None
    quest_id: UUID | None = None
    try:
        base = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=base, timeout=2) as client:
            for _ in range(100):
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.05)
            else:
                pytest.fail("Temporary API process did not become ready")
            created = client.post("/api/guest-sessions", json={"confirm_adult": True}, headers={"Origin": ORIGIN})
            assert created.status_code == 200
            identity = UUID(created.json()["identity_id"])
            identities.add(identity)
            session_cookie = client.cookies.get(COOKIE_NAME)
            assert session_cookie
            created_quest = client.post("/api/quests", json={"lesson_id": "german-a1-greetings", "concept_ids": ["german-greetings"], "template_id": "concept-guide-v1"}, headers={"Origin": ORIGIN, "Idempotency-Key": "process-restart-quest"})
            assert created_quest.status_code == 200
            quest_id = UUID(created_quest.json()["quest_id"])
            quest_ids.add(quest_id)
        process.terminate()
        process.wait(timeout=5)
        process = start_server()
        with httpx.Client(base_url=base, timeout=2) as client:
            for _ in range(100):
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.05)
            else:
                pytest.fail("Restarted API process did not become ready")
            assert session_cookie and quest_id
            client.cookies.set(COOKIE_NAME, session_cookie)
            persisted = client.get(f"/api/quests/{quest_id}")
            assert persisted.status_code == 200, persisted.text
            assert persisted.json()["quest_id"] == str(quest_id)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


PRACTICE_ANSWERS = {
    "german-a1-greeting-time": "option-a",
    "german-a1-introduce-name": "option-a",
    "german-a1-formal-name-question": "option-b",
    "german-a1-match-greetings": [
        {"left_id": "guten-morgen", "right_id": "good-morning"},
        {"left_id": "guten-tag", "right_id": "good-day"},
        {"left_id": "tschuss", "right_id": "bye"},
    ],
    "german-a1-fill-name-verb": "heiße",
    "german-a1-fill-formal-verb": "heißen",
    "german-a1-fill-goodbye": "Tschüss",
}


def collaborate(host: TestClient, partner: TestClient, quest_ids: set[UUID], key: str = "collab") -> UUID:
    guest(host, set())
    guest(partner, set())
    quest_id = create_quest(host, quest_ids, f"{key}-create")
    invitation = host.post(
        f"/api/quests/{quest_id}/invitations",
        headers={"Origin": ORIGIN, "Idempotency-Key": f"{key}-invite"},
    ).json()
    redeemed = partner.post(
        "/api/quest-invitations/redeem",
        json={"token": invitation["invitation_token"], "confirm_adult": True},
        headers={"Origin": ORIGIN, "Idempotency-Key": f"{key}-redeem"},
    )
    assert redeemed.status_code == 200, redeemed.text
    return quest_id


def submit_preparation(client: TestClient, quest_id: UUID, exercise_id: str, answer: object):
    return client.post(
        f"/api/quests/{quest_id}/preparation/check",
        json={"exercise_id": exercise_id, "answer": answer},
        headers={"Origin": ORIGIN},
    )


def finish_preparation(client: TestClient, quest_id: UUID, limit: int = 7) -> None:
    for exercise_id, answer in list(PRACTICE_ANSWERS.items())[:limit]:
        response = submit_preparation(client, quest_id, exercise_id, answer)
        assert response.status_code == 200 and response.json()["correct"], response.text


def test_preparation_is_independent_checked_and_duplicate_safe(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "prep-independent")
        forged = host.post(
            f"/api/quests/{quest_id}/preparation/check",
            json={"exercise_id": "german-a1-greeting-time", "answer": "option-a", "correct": True,
                  "identity_id": "00000000-0000-0000-0000-000000000001", "evidence_id": "forged"},
            headers={"Origin": ORIGIN},
        )
        assert forged.status_code == 422
        assert submit_preparation(host, quest_id, "made-up-exercise", "option-a").status_code == 404
        wrong = submit_preparation(host, quest_id, "german-a1-greeting-time", "option-b")
        assert wrong.status_code == 200 and wrong.json()["correct"] is False
        finish_preparation(host, quest_id)
        replay = submit_preparation(host, quest_id, "german-a1-greeting-time", "option-a")
        assert replay.status_code == 200 and replay.json()["member_checked_count"] == 7
        assert host.get(f"/api/quests/{quest_id}").json()["state"] == "preparing"
        waiting = partner.get(f"/api/quests/{quest_id}/preparation")
        assert waiting.status_code == 200
        assert next(item for item in waiting.json()["members"] if item["role"] == "collaborator")["checked_count"] == 0
        finish_preparation(partner, quest_id, limit=6)
        assert partner.get(f"/api/quests/{quest_id}").json()["state"] == "preparing"
        final = submit_preparation(partner, quest_id, "german-a1-fill-goodbye", "Tschüss")
        assert final.status_code == 200 and final.json()["quest_state"] == "collaborating"
        assert host.get(f"/api/quests/{quest_id}").json()["state"] == "collaborating"
        status = host.get(f"/api/quests/{quest_id}/preparation").json()
        assert all(member["complete"] and member["checked_count"] == 7 for member in status["members"])
        artifact = host.get(f"/api/quests/{quest_id}/artifact")
        assert artifact.status_code == 200
        assert artifact.json()["current_revision"] == 0
        with Session(get_engine()) as db:
            count = db.scalar(select(text("count(*)")).select_from(QuestPreparationEvidence.__table__).where(QuestPreparationEvidence.quest_id == quest_id))
            assert count == 14


def test_preparation_and_artifact_authorization_and_gating(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner, TestClient(app) as outsider:
        guest(outsider, identities)
        quest_id = collaborate(host, partner, quest_ids, "prep-gating")
        assert host.get(f"/api/quests/{quest_id}/artifact").status_code == 409
        assert outsider.get(f"/api/quests/{quest_id}/preparation").status_code == 404
        assert outsider.get(f"/api/quests/{quest_id}/artifact").status_code == 404
        assert outsider.post(f"/api/quests/{quest_id}/preparation/check", json={
            "exercise_id": "german-a1-greeting-time", "answer": "option-a"
        }, headers={"Origin": ORIGIN}).status_code == 404


def _artifact_request(client: TestClient, quest_id: UUID, section: str, revision: int, content: object, key: str):
    return client.patch(
        f"/api/quests/{quest_id}/artifact/sections/{section}",
        json={"expected_revision": revision, "content": content},
        headers={"Origin": ORIGIN, "Idempotency-Key": key},
    )


def test_artifact_revisions_are_atomic_immutable_idempotent_and_persistent(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "artifact-revisions")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id)
        initial = host.get(f"/api/quests/{quest_id}/artifact").json()
        first = _artifact_request(host, quest_id, "explanation", 0, "Use ich heiße to introduce your name.", "save-explain-1")
        assert first.status_code == 200 and first.json()["revision_number"] == 1
        replay = _artifact_request(host, quest_id, "explanation", 0, "Use ich heiße to introduce your name.", "save-explain-1")
        assert replay.status_code == 200 and replay.json()["revision_number"] == 1
        reused = _artifact_request(host, quest_id, "explanation", 0, "Changed payload.", "save-explain-1")
        assert reused.status_code == 409 and reused.json()["code"] == "idempotency_key_reused"
        stale = _artifact_request(partner, quest_id, "example", 0, "Ich heiße Ada.", "save-example-stale")
        assert stale.status_code == 409
        assert stale.json()["current_revision"] == 1
        second_author = _artifact_request(partner, quest_id, "example", 1, "Ich heiße Ada.", "save-example-2")
        assert second_author.status_code == 200
        assert second_author.json()["author_role"] == "collaborator"
        shared = host.get(f"/api/quests/{quest_id}/artifact").json()
        assert shared["current_revision"] == 2
        assert {row["author_role"] for row in shared["revisions"] if row["revision_number"] > 0} == {"host", "collaborator"}
        with Session(get_engine()) as db:
            revision = db.scalar(select(QuestArtifactRevision).where(
                QuestArtifactRevision.quest_id == quest_id, QuestArtifactRevision.revision_number == 1
            ))
            assert revision and revision.snapshot["explanation"] == "Use ich heiße to introduce your name."
            with pytest.raises(DBAPIError):
                db.execute(update(QuestArtifactRevision).where(QuestArtifactRevision.id == revision.id).values(snapshot=initial["snapshot"]))
                db.commit()
            db.rollback()
            with pytest.raises(DBAPIError):
                db.execute(delete(QuestArtifactRevision).where(QuestArtifactRevision.id == revision.id))
                db.commit()
            db.rollback()
        assert host.get(f"/api/quests/{quest_id}/artifact").json()["current_revision"] == 2
        dispose_engine()
        persisted = host.get(f"/api/quests/{quest_id}/artifact")
        assert persisted.status_code == 200 and persisted.json()["current_revision"] == 2


def test_concurrent_artifact_edits_allow_one_revision_and_report_conflict(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "artifact-race")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id)
        cookies = [host.cookies.get(COOKIE_NAME), partner.cookies.get(COOKIE_NAME)]
        assert all(cookies)

        def edit(args):
            cookie, text_value, key = args
            with TestClient(app) as client:
                client.cookies.set(COOKIE_NAME, cookie)
                return _artifact_request(client, quest_id, "example", 0, text_value, key)

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(edit, zip(cookies, ["Ich heiße Ada.", "Wie heißt du?"], ["race-a", "race-b"])))
        assert sorted(response.status_code for response in responses) == [200, 409]
        conflict = next(response for response in responses if response.status_code == 409)
        assert conflict.json()["current_revision"] == 1
        current = host.get(f"/api/quests/{quest_id}/artifact").json()
        assert current["current_revision"] == 1
        assert len([row for row in current["revisions"] if row["revision_number"] > 0]) == 1


def test_artifact_survives_real_api_process_restart(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "artifact-process-restart")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id)
        saved = _artifact_request(host, quest_id, "explanation", 0, "Use heiße to give your name.", "restart-save")
        assert saved.status_code == 200
        cookie = host.cookies.get(COOKIE_NAME)
        assert cookie

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": "apps/api",
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "QUEST_SESSION_SECRET": "local-integration-test-secret-at-least-32-bytes",
        "WEB_ORIGIN": ORIGIN,
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", str(port)],
        cwd=os.getcwd(), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3) as client:
            for _ in range(100):
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.05)
            else:
                pytest.fail("Temporary API process did not become ready")
            response = client.get(f"/api/quests/{quest_id}/artifact", cookies={COOKIE_NAME: cookie})
            assert response.status_code == 200
            assert response.json()["current_revision"] == 1
            assert response.json()["snapshot"]["explanation"] == "Use heiße to give your name."
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_artifact_limits_and_failed_collaboration_transition_roll_back(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "artifact-rollback")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id, limit=6)
        assert host.get(f"/api/quests/{quest_id}").json()["state"] == "preparing"

        engine = get_engine()
        with engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION fail_test_artifact_insert() RETURNS trigger AS $$
                BEGIN RAISE EXCEPTION 'test-only artifact failure'; END;
                $$ LANGUAGE plpgsql
            """)
            connection.exec_driver_sql("""
                CREATE TRIGGER fail_test_artifact_insert BEFORE INSERT ON quest_artifacts
                FOR EACH ROW EXECUTE FUNCTION fail_test_artifact_insert()
            """)
        try:
            with Session(get_engine()) as db:
                final_identity = authenticate_cookie_identity(db, partner.cookies.get(COOKIE_NAME))
            with TestClient(app, raise_server_exceptions=False) as client:
                client.cookies.set(COOKIE_NAME, partner.cookies.get(COOKIE_NAME))
                failed = submit_preparation(client, quest_id, "german-a1-fill-goodbye", "Tschüss")
            assert failed.status_code == 503
            with Session(get_engine()) as db:
                assert db.get(Quest, quest_id).state == "preparing"
                assert db.scalar(select(QuestArtifact).where(QuestArtifact.quest_id == quest_id)) is None
                assert db.scalar(select(QuestPreparationEvidence).where(
                    QuestPreparationEvidence.quest_id == quest_id,
                    QuestPreparationEvidence.identity_id == final_identity,
                    QuestPreparationEvidence.evidence_id == "german-informal-goodbye",
                )) is None
        finally:
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS fail_test_artifact_insert ON quest_artifacts")
                connection.exec_driver_sql("DROP FUNCTION IF EXISTS fail_test_artifact_insert()")



def test_artifact_field_limits_are_enforced(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "artifact-limits")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id)
        oversized = _artifact_request(host, quest_id, "explanation", 0, "x" * 2001, "too-large-explanation")
        assert oversized.status_code == 422
        invalid_pair = _artifact_request(host, quest_id, "misconception_correction", 0,
                                         {"misconception": "x" * 1201, "correction": "y"}, "too-large-correction")
        assert invalid_pair.status_code == 422


def test_expired_collaboration_is_read_only_and_keeps_derived_expiry_semantics(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "collaboration-expiry")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id)
        with Session(get_engine()) as db, db.begin():
            quest = db.get(Quest, quest_id)
            quest.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert host.get(f"/api/quests/{quest_id}").json()["state"] == "expired"
        assert host.get(f"/api/quests/{quest_id}/preparation").json()["state"] == "expired"
        assert host.get(f"/api/quests/{quest_id}/artifact").status_code == 409
        assert _artifact_request(host, quest_id, "explanation", 0, "Late edit.", "expired-edit").status_code == 409


def authenticate_cookie_identity(db: Session, cookie: str) -> UUID:
    token_hash = hashlib.sha256(cookie.encode()).hexdigest()
    return db.scalar(select(GuestSession.identity_id).where(GuestSession.token_hash == token_hash))


def make_review_ready(host: TestClient, partner: TestClient, quest_ids: set[UUID], key: str) -> UUID:
    quest_id = collaborate(host, partner, quest_ids, key)
    finish_preparation(host, quest_id)
    finish_preparation(partner, quest_id)
    first = _artifact_request(host, quest_id, "explanation", 0, "Use ich heiße to introduce your name.", f"{key}-host-edit")
    second = _artifact_request(partner, quest_id, "example", 1, "Guten Tag, ich heiße Ada.", f"{key}-partner-edit")
    assert first.status_code == second.status_code == 200
    return quest_id


def peer_review_body(revision_id: str) -> dict[str, object]:
    return {
        "revision_id": revision_id,
        "rubric_version": "peer-review-v1",
        "conceptual_correctness": "clear",
        "explanation_clarity": "mostly_there",
        "example_relevance": "clear",
        "misconception_correction": "mostly_there",
        "follow_up_usefulness": "needs_work",
        "strength": "The example uses the phrase in a natural introduction.",
        "improvement_suggestion": "Add a short translation beside the example.",
        "rationale": "The meaning is accurate, and a translation would help a beginner follow it.",
    }


def post_peer_review(client: TestClient, quest_id: UUID, body: dict[str, object], key: str):
    return client.post(
        f"/api/quests/{quest_id}/reviews", json=body,
        headers={"Origin": ORIGIN, "Idempotency-Key": key},
    )


def test_peer_reviews_are_reciprocal_revision_bound_immutable_and_one_round_only(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = collaborate(host, partner, quest_ids, "peer-review-reciprocal")
        finish_preparation(host, quest_id)
        finish_preparation(partner, quest_id)
        assert host.get(f"/api/quests/{quest_id}/reviews").json()["eligible"] is False
        host_edit = _artifact_request(host, quest_id, "explanation", 0, "Use ich heiße to introduce your name.", "peer-host-rev")
        partner_edit = _artifact_request(partner, quest_id, "example", 1, "Guten Tag, ich heiße Ada.", "peer-partner-rev")
        assert host_edit.status_code == partner_edit.status_code == 200
        host_status = host.get(f"/api/quests/{quest_id}/reviews").json()
        partner_status = partner.get(f"/api/quests/{quest_id}/reviews").json()
        assert host_status["eligible"] and partner_status["eligible"]
        assert host_status["reviewable_revision"]["revision_id"] == partner_edit.json()["revision_id"]
        assert partner_status["reviewable_revision"]["revision_id"] == host_edit.json()["revision_id"]

        host_body = peer_review_body(partner_edit.json()["revision_id"])
        submitted_host = post_peer_review(host, quest_id, host_body, "peer-host-review")
        assert submitted_host.status_code == 200, submitted_host.text
        assert submitted_host.json()["revision_number"] == 2
        assert submitted_host.json()["snapshot"]["example"] == "Guten Tag, ich heiße Ada."
        received_by_partner = partner.get(f"/api/quests/{quest_id}/reviews").json()["review_received"]
        assert received_by_partner["review_id"] == submitted_host.json()["review_id"]
        assert received_by_partner["strength"] == host_body["strength"]
        replay = post_peer_review(host, quest_id, host_body, "peer-host-review")
        assert replay.status_code == 200 and replay.json()["review_id"] == submitted_host.json()["review_id"]
        changed_replay = dict(host_body, strength="A different strength.")
        changed = post_peer_review(host, quest_id, changed_replay, "peer-host-review")
        assert changed.status_code == 409 and changed.json()["code"] == "idempotency_key_reused"
        duplicate = post_peer_review(host, quest_id, host_body, "peer-host-review-second-key")
        assert duplicate.status_code == 409 and duplicate.json()["code"] == "review_already_submitted"

        partner_body = peer_review_body(host_edit.json()["revision_id"])
        submitted_partner = post_peer_review(partner, quest_id, partner_body, "peer-partner-review")
        assert submitted_partner.status_code == 200, submitted_partner.text
        assert host.get(f"/api/quests/{quest_id}/reviews").json()["review_received"]["review_id"] == submitted_partner.json()["review_id"]

        later_edit = _artifact_request(partner, quest_id, "follow_up_question", 2, "Can you introduce yourself?", "peer-later-revision")
        assert later_edit.status_code == 200
        status = host.get(f"/api/quests/{quest_id}/reviews").json()
        assert status["review_given"]["revision_is_current"] is False
        assert status["review_given"]["snapshot"]["example"] == "Guten Tag, ich heiße Ada."
        assert status["reviewable_revision"] is None
        second_round = post_peer_review(host, quest_id, peer_review_body(later_edit.json()["revision_id"]), "peer-no-round-two")
        assert second_round.status_code == 409 and second_round.json()["code"] == "review_already_submitted"
        with Session(get_engine()) as db:
            stored = db.scalar(select(QuestArtifactReview).where(QuestArtifactReview.id == UUID(submitted_host.json()["review_id"])))
            assert stored is not None and stored.artifact_revision_id == UUID(partner_edit.json()["revision_id"])
            with pytest.raises(DBAPIError):
                db.execute(update(QuestArtifactReview).where(QuestArtifactReview.id == stored.id).values(strength="rewritten"))
                db.commit()
            db.rollback()
            with pytest.raises(DBAPIError):
                db.execute(delete(QuestArtifactReview).where(QuestArtifactReview.id == stored.id))
                db.commit()
            db.rollback()


def test_peer_review_rejects_self_stale_and_cross_quest_access(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner, TestClient(app) as outsider:
        guest(outsider, identities)
        quest_id = make_review_ready(host, partner, quest_ids, "peer-review-targets")
        revisions = host.get(f"/api/quests/{quest_id}/artifact").json()["revisions"]
        host_revision = next(row for row in revisions if row["author_role"] == "host")
        partner_revision = next(row for row in revisions if row["author_role"] == "collaborator")
        self_review = post_peer_review(host, quest_id, peer_review_body(host_revision["revision_id"]), "peer-self")
        assert self_review.status_code == 409 and self_review.json()["code"] == "self_review_not_allowed"
        invalid_rating = post_peer_review(host, quest_id, dict(peer_review_body(partner_revision["revision_id"]), conceptual_correctness="excellent"), "peer-invalid-rating")
        assert invalid_rating.status_code == 422
        forged_member = post_peer_review(host, quest_id, dict(peer_review_body(partner_revision["revision_id"]), recipient_identity_id="forged"), "peer-forged-member")
        assert forged_member.status_code == 422
        newer = _artifact_request(partner, quest_id, "follow_up_question", 2, "What is your name?", "peer-new-target")
        assert newer.status_code == 200
        stale = post_peer_review(host, quest_id, peer_review_body(partner_revision["revision_id"]), "peer-stale-target")
        assert stale.status_code == 409 and stale.json()["code"] == "review_target_changed"
        assert stale.json()["current_reviewable_revision"] == {
            "revision_id": newer.json()["revision_id"],
            "revision_number": newer.json()["revision_number"],
        }
        assert outsider.get(f"/api/quests/{quest_id}/reviews").status_code == 404
        unauthorized_post = outsider.post(f"/api/quests/{quest_id}/reviews", json=peer_review_body(newer.json()["revision_id"]), headers={"Origin": ORIGIN, "Idempotency-Key": "outsider-review"})
        assert unauthorized_post.status_code == 404
        valid_review = post_peer_review(host, quest_id, peer_review_body(newer.json()["revision_id"]), "peer-valid-before-cross-quest")
        assert valid_review.status_code == 200
        other_quest_id = create_quest(partner, quest_ids, "peer-other-quest")
        assert host.get(f"/api/quests/{other_quest_id}/reviews").status_code == 404
        cross_quest_ack = partner.post(
            f"/api/quests/{other_quest_id}/reviews/{valid_review.json()['review_id']}/acknowledgement",
            json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "cross-quest-ack"},
        )
        assert cross_quest_ack.status_code == 404

        # A mismatched recipient cannot be stored, even when inserted outside the API.
        outsider_id = next(iter(identities))
        reviewer_id = authenticate_cookie_identity(db := Session(get_engine()), host.cookies.get(COOKIE_NAME))
        try:
            artifact = db.scalar(select(QuestArtifact).where(QuestArtifact.quest_id == quest_id))
            partner_revision_row = db.get(QuestArtifactRevision, UUID(newer.json()["revision_id"]))
            assert artifact is not None and partner_revision_row is not None
            forged = QuestArtifactReview(
                id=uuid4(), quest_id=quest_id, artifact_id=artifact.id,
                artifact_revision_id=partner_revision_row.id, reviewer_identity_id=reviewer_id,
                recipient_identity_id=outsider_id, rubric_version="peer-review-v1",
                conceptual_correctness="clear", explanation_clarity="clear", example_relevance="clear",
                misconception_correction="clear", follow_up_usefulness="clear", strength="A valid strength.",
                improvement_suggestion="A valid suggestion.", rationale="A valid rationale.",
                idempotency_key_hash="f" * 64, request_hash="e" * 64, created_at=datetime.now(timezone.utc),
            )
            db.add(forged)
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
        finally:
            db.close()


def test_peer_review_acknowledgement_and_response_are_authorized_write_once(test_database) -> None:
    identities, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner, TestClient(app) as outsider:
        guest(outsider, identities)
        quest_id = make_review_ready(host, partner, quest_ids, "peer-review-response")
        target = host.get(f"/api/quests/{quest_id}/reviews").json()["reviewable_revision"]["revision_id"]
        review = post_peer_review(host, quest_id, peer_review_body(target), "peer-review-for-response")
        assert review.status_code == 200
        review_id = review.json()["review_id"]
        ack_url = f"/api/quests/{quest_id}/reviews/{review_id}/acknowledgement"
        response_url = f"/api/quests/{quest_id}/reviews/{review_id}/response"
        assert host.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "wrong-recipient-ack"}).status_code == 404
        assert outsider.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "outsider-ack"}).status_code == 404
        before_ack = partner.post(response_url, json={"response": "Thanks"}, headers={"Origin": ORIGIN, "Idempotency-Key": "reply-before-ack"})
        assert before_ack.status_code == 409 and before_ack.json()["code"] == "review_acknowledgement_required"
        acknowledged = partner.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "review-ack"})
        assert acknowledged.status_code == 200
        replay_ack = partner.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "review-ack"})
        assert replay_ack.status_code == 200
        assert datetime.fromisoformat(replay_ack.json()["acknowledged_at"]) == datetime.fromisoformat(acknowledged.json()["acknowledged_at"])
        assert partner.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "second-ack-key"}).status_code == 409

        response_body = {"response": "Thank you. I will add the translation."}
        saved_response = partner.post(response_url, json=response_body, headers={"Origin": ORIGIN, "Idempotency-Key": "review-response"})
        assert saved_response.status_code == 200 and saved_response.json()["response_text"] == response_body["response"]
        assert partner.post(response_url, json=response_body, headers={"Origin": ORIGIN, "Idempotency-Key": "review-response"}).status_code == 200
        changed = partner.post(response_url, json={"response": "Changed"}, headers={"Origin": ORIGIN, "Idempotency-Key": "review-response"})
        assert changed.status_code == 409 and changed.json()["code"] == "idempotency_key_reused"
        assert partner.post(response_url, json={"response": "Another reply"}, headers={"Origin": ORIGIN, "Idempotency-Key": "second-response-key"}).status_code == 409
        assert host.get(f"/api/quests/{quest_id}/reviews").json()["review_given"]["response_text"] == response_body["response"]
        with Session(get_engine()) as db:
            stored_review = db.get(QuestArtifactReview, UUID(review_id))
            assert stored_review is not None
            stored_response = db.get(QuestArtifactReviewResponse, stored_review.id)
            assert stored_response is not None
            with pytest.raises(DBAPIError):
                db.execute(update(QuestArtifactReviewResponse).where(QuestArtifactReviewResponse.review_id == stored_review.id).values(acknowledged_at=datetime.now(timezone.utc)))
                db.commit()
            db.rollback()
            with pytest.raises(DBAPIError):
                db.execute(update(QuestArtifactReviewResponse).where(QuestArtifactReviewResponse.review_id == stored_review.id).values(response_text="rewritten"))
                db.commit()
            db.rollback()
            with pytest.raises(DBAPIError):
                db.execute(delete(QuestArtifactReviewResponse).where(QuestArtifactReviewResponse.review_id == stored_review.id))
                db.commit()
            db.rollback()


def test_concurrent_reciprocal_reviews_and_exact_retry_are_idempotent(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = make_review_ready(host, partner, quest_ids, "peer-review-concurrent")
        host_target = host.get(f"/api/quests/{quest_id}/reviews").json()["reviewable_revision"]["revision_id"]
        partner_target = partner.get(f"/api/quests/{quest_id}/reviews").json()["reviewable_revision"]["revision_id"]
        cookies = [host.cookies.get(COOKIE_NAME), partner.cookies.get(COOKIE_NAME)]
        assert all(cookies)

        def send(args):
            cookie, target, key = args
            with TestClient(app) as client:
                client.cookies.set(COOKIE_NAME, cookie)
                return post_peer_review(client, quest_id, peer_review_body(target), key)

        with ThreadPoolExecutor(max_workers=2) as pool:
            reciprocal = list(pool.map(send, [(cookies[0], host_target, "concurrent-host-review"), (cookies[1], partner_target, "concurrent-partner-review")]))
        assert [response.status_code for response in reciprocal] == [200, 200]
        with ThreadPoolExecutor(max_workers=2) as pool:
            retries = list(pool.map(send, [(cookies[0], host_target, "concurrent-host-review")] * 2))
        assert [response.status_code for response in retries] == [200, 200]
        assert retries[0].json()["review_id"] == retries[1].json()["review_id"]
        with Session(get_engine()) as db:
            assert db.scalar(select(func.count()).select_from(QuestArtifactReview).where(QuestArtifactReview.quest_id == quest_id)) == 2


def test_peer_review_database_failure_rolls_back_and_expiry_is_read_only(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = make_review_ready(host, partner, quest_ids, "peer-review-rollback")
        target = host.get(f"/api/quests/{quest_id}/reviews").json()["reviewable_revision"]["revision_id"]
        engine = get_engine()
        with engine.begin() as connection:
            connection.execute(text("CREATE FUNCTION fail_peer_review_insert_for_test() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'test review insert failure'; END; $$ LANGUAGE plpgsql"))
            connection.execute(text("CREATE TRIGGER fail_peer_review_insert_for_test BEFORE INSERT ON quest_artifact_reviews FOR EACH ROW EXECUTE FUNCTION fail_peer_review_insert_for_test()"))
        try:
            failed = post_peer_review(host, quest_id, peer_review_body(target), "peer-review-failure")
            assert failed.status_code == 503
            assert host.get(f"/api/quests/{quest_id}/reviews").json()["submitted_by_you"] is False
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(QuestArtifactReview).where(QuestArtifactReview.quest_id == quest_id)) == 0
        finally:
            with engine.begin() as connection:
                connection.execute(text("DROP TRIGGER IF EXISTS fail_peer_review_insert_for_test ON quest_artifact_reviews"))
                connection.execute(text("DROP FUNCTION IF EXISTS fail_peer_review_insert_for_test()"))
        saved = post_peer_review(host, quest_id, peer_review_body(target), "peer-review-before-expiry")
        assert saved.status_code == 200
        with Session(engine) as db, db.begin():
            quest = db.get(Quest, quest_id)
            assert quest is not None
            quest.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        status = host.get(f"/api/quests/{quest_id}/reviews")
        assert status.status_code == 200 and status.json()["state"] == "expired"
        assert status.json()["review_given"]["review_id"] == saved.json()["review_id"]
        expired_write = post_peer_review(partner, quest_id, peer_review_body(target), "peer-review-expired-write")
        assert expired_write.status_code == 409
        ack = partner.post(f"/api/quests/{quest_id}/reviews/{saved.json()['review_id']}/acknowledgement", json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "peer-expired-ack"})
        assert ack.status_code == 409


def test_peer_review_idempotent_retries_after_expiry(test_database) -> None:
    _, quest_ids = test_database
    with TestClient(app) as host, TestClient(app) as partner:
        quest_id = make_review_ready(host, partner, quest_ids, "peer-review-expiry-replay")
        host_target = host.get(f"/api/quests/{quest_id}/reviews").json()["reviewable_revision"]["revision_id"]
        partner_target = partner.get(f"/api/quests/{quest_id}/reviews").json()["reviewable_revision"]["revision_id"]

        host_body = peer_review_body(host_target)
        host_review = post_peer_review(host, quest_id, host_body, "expiry-replay-host-review")
        partner_review = post_peer_review(partner, quest_id, peer_review_body(partner_target), "expiry-replay-partner-review")
        assert host_review.status_code == partner_review.status_code == 200

        review_id = host_review.json()["review_id"]
        ack_url = f"/api/quests/{quest_id}/reviews/{review_id}/acknowledgement"
        response_url = f"/api/quests/{quest_id}/reviews/{review_id}/response"
        ack_key = "expiry-replay-ack"
        response_key = "expiry-replay-response"
        response_body = {"response": "I will add the translation."}
        acknowledged = partner.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": ack_key})
        saved_response = partner.post(response_url, json=response_body, headers={"Origin": ORIGIN, "Idempotency-Key": response_key})
        assert acknowledged.status_code == saved_response.status_code == 200

        with Session(get_engine()) as db, db.begin():
            quest = db.get(Quest, quest_id)
            assert quest is not None
            quest.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        review_retry = post_peer_review(host, quest_id, host_body, "expiry-replay-host-review")
        assert review_retry.status_code == 200
        assert review_retry.json()["review_id"] == host_review.json()["review_id"]
        changed_review = post_peer_review(host, quest_id, dict(host_body, strength="A changed payload."), "expiry-replay-host-review")
        assert changed_review.status_code == 409 and changed_review.json()["code"] == "idempotency_key_reused"
        new_review = post_peer_review(host, quest_id, host_body, "expiry-replay-new-review-key")
        assert new_review.status_code == 409 and new_review.json()["code"] == "quest_expired"

        ack_retry = partner.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": ack_key})
        assert ack_retry.status_code == 200
        assert datetime.fromisoformat(ack_retry.json()["acknowledged_at"]) == datetime.fromisoformat(acknowledged.json()["acknowledged_at"])
        malformed_ack_retry = partner.post(ack_url, json={"extra": "different payload"}, headers={"Origin": ORIGIN, "Idempotency-Key": ack_key})
        assert malformed_ack_retry.status_code == 422
        new_ack = partner.post(ack_url, json={}, headers={"Origin": ORIGIN, "Idempotency-Key": "expiry-replay-new-ack-key"})
        assert new_ack.status_code == 409 and new_ack.json()["code"] == "quest_expired"

        response_retry = partner.post(response_url, json=response_body, headers={"Origin": ORIGIN, "Idempotency-Key": response_key})
        assert response_retry.status_code == 200
        assert response_retry.json()["response_text"] == saved_response.json()["response_text"]
        changed_response = partner.post(response_url, json={"response": "A different response."}, headers={"Origin": ORIGIN, "Idempotency-Key": response_key})
        assert changed_response.status_code == 409 and changed_response.json()["code"] == "idempotency_key_reused"
        new_response = partner.post(response_url, json={"response": "A new response."}, headers={"Origin": ORIGIN, "Idempotency-Key": "expiry-replay-new-response-key"})
        assert new_response.status_code == 409 and new_response.json()["code"] == "quest_expired"
