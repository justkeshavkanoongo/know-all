from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
EXPECTED_COURSES = {
    "german": "German",
    "french": "French",
    "literature": "Literature",
    "psychology": "Psychology",
    "philosophy": "Philosophy",
}


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "know-all-api"}


def test_catalog_contains_exactly_the_five_approved_courses() -> None:
    response = client.get("/api/courses")

    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 5
    assert {course["slug"]: course["title"] for course in courses} == EXPECTED_COURSES
    assert all(course["id"] and course["description"] for course in courses)
    assert all(course["level_count"] > 0 and course["module_count"] > 0 for course in courses)


def test_each_course_has_a_detail_and_representative_modules() -> None:
    summaries = client.get("/api/courses").json()

    for summary in summaries:
        response = client.get(f"/api/courses/{summary['slug']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["id"] == summary["id"]
        assert detail["slug"] == summary["slug"]
        assert detail["learning_rationale"]
        assert "representative" in detail["curriculum_note"].lower()
        assert detail["levels"]
        assert all(level["modules"] for level in detail["levels"])


def test_german_and_french_show_cefr_pathway_without_claiming_completion() -> None:
    for slug in ("german", "french"):
        detail = client.get(f"/api/courses/{slug}").json()
        assert [level["label"] for level in detail["levels"]] == [
            "A1", "A2", "B1", "B2", "C1", "C2"
        ]
        assert "representative" in detail["curriculum_note"].lower()


def test_unknown_course_slug_returns_predictable_404() -> None:
    response = client.get("/api/courses/not-a-course")

    assert response.status_code == 404
    assert response.json() == {
        "code": "course_not_found",
        "message": "No course was found for slug 'not-a-course'.",
    }
