from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

from .catalog import get_course_by_slug, list_course_summaries
from .assessment_models import (
    AssessmentAttemptRequest,
    AssessmentResult,
    AssessmentSubmitRequest,
    PublicAssessmentAttempt,
)
from .assessments import (
    AssessmentAttemptAlreadySubmitted,
    AssessmentAttemptNotFound,
    AssessmentBankExhausted,
    InvalidAssessmentAnswer,
    create_assessment_attempt,
    submit_assessment,
)
from .lessons import get_lesson
from .lesson_models import LessonDetail
from .models import ApiError, CourseDetail, CourseSummary, HealthResponse
from .practice import (
    IncompatiblePracticeAnswer,
    check_practice_answer,
    get_practice_set,
)
from .practice_models import PracticeCheckRequest, PracticeCheckResponse, PracticeSet
from .quests import router as quest_router
from .database import DatabaseConfigurationError

app = FastAPI(
    title="Know It All API",
    version="1.0.0",
    description="A small, typed API for the Know It All course catalog.",
)
app.include_router(quest_router)


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Never return connection details or SQL to clients.
    return JSONResponse(status_code=503, content={"code": "database_unavailable", "message": "The quest service is temporarily unavailable."})


@app.exception_handler(DatabaseConfigurationError)
async def database_not_configured(request: Request, exc: DatabaseConfigurationError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"code": "database_unavailable", "message": "The quest service is not configured."})


@app.exception_handler(StarletteHTTPException)
async def predictable_http_errors(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        error = ApiError.model_validate(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=error.model_dump(exclude_none=True))
    return await http_exception_handler(request, exc)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="know-all-api")


@app.get("/api/courses", response_model=tuple[CourseSummary, ...], tags=["courses"])
def list_courses() -> tuple[CourseSummary, ...]:
    return list_course_summaries()


@app.get(
    "/api/courses/{slug}",
    response_model=CourseDetail,
    responses={404: {"model": ApiError, "description": "Course slug was not found."}},
    tags=["courses"],
)
def course_detail(slug: str) -> CourseDetail:
    course = get_course_by_slug(slug)
    if course is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "course_not_found",
                "message": f"No course was found for slug '{slug}'.",
            },
        )
    return course


@app.get(
    "/api/lessons/{lesson_id}",
    response_model=LessonDetail,
    responses={404: {"model": ApiError, "description": "Lesson ID was not found."}},
    tags=["lessons"],
)
def lesson_detail(lesson_id: str) -> LessonDetail:
    lesson = get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "lesson_not_found",
                "message": f"No lesson was found for ID '{lesson_id}'.",
            },
        )
    return lesson


@app.get(
    "/api/lessons/{lesson_id}/practice",
    response_model=PracticeSet,
    responses={404: {"model": ApiError, "description": "Lesson ID was not found."}},
    tags=["practice"],
)
def lesson_practice(lesson_id: str) -> PracticeSet:
    if get_lesson(lesson_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "lesson_not_found", "message": "Lesson was not found."},
        )
    practice_set = get_practice_set(lesson_id)
    if practice_set is None:
        return PracticeSet(
            lesson_id=lesson_id,
            exercise_set_id=f"{lesson_id}-practice",
            version="1.0.0",
            exercises=(),
        )
    return practice_set


@app.post(
    "/api/lessons/{lesson_id}/practice/check",
    response_model=PracticeCheckResponse,
    responses={
        400: {"model": ApiError, "description": "Answer is incompatible with this exercise."},
        404: {"model": ApiError, "description": "Lesson or exercise was not found."},
    },
    tags=["practice"],
)
def check_lesson_practice(
    lesson_id: str, request: PracticeCheckRequest
) -> PracticeCheckResponse:
    if get_lesson(lesson_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "lesson_not_found", "message": "Lesson was not found."},
        )
    try:
        result = check_practice_answer(lesson_id, request.exercise_id, request.answer)
    except IncompatiblePracticeAnswer as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "incompatible_practice_answer",
                "message": str(exc),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_practice_answer", "message": str(exc)},
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "exercise_not_found",
                "message": "Exercise was not found for this lesson.",
            },
        )
    return result


@app.post(
    "/api/lessons/{lesson_id}/assessment-attempts",
    response_model=PublicAssessmentAttempt,
    responses={
        404: {"model": ApiError, "description": "Lesson ID was not found."},
        409: {"model": ApiError, "description": "No fresh 15-question set is available."},
    },
    tags=["assessment"],
)
def create_lesson_assessment(
    lesson_id: str, request: AssessmentAttemptRequest
) -> PublicAssessmentAttempt:
    try:
        return create_assessment_attempt(lesson_id, request.exclude_question_ids)
    except AssessmentAttemptNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "lesson_not_found", "message": "Lesson was not found."},
        ) from exc
    except AssessmentBankExhausted as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "assessment_bank_exhausted",
                "message": "A fresh set of 15 distinct reviewed questions is not available yet.",
            },
        ) from exc


@app.post(
    "/api/lessons/{lesson_id}/assessment-attempts/{attempt_id}/submit",
    response_model=AssessmentResult,
    responses={
        404: {"model": ApiError, "description": "Lesson or attempt was not found."},
        409: {"model": ApiError, "description": "Attempt has already been submitted."},
        422: {"model": ApiError, "description": "Answer set is invalid."},
    },
    tags=["assessment"],
)
def submit_lesson_assessment(
    lesson_id: str, attempt_id: str, request: AssessmentSubmitRequest
) -> AssessmentResult:
    try:
        return submit_assessment(lesson_id, attempt_id, request.answers)
    except AssessmentAttemptNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "attempt_not_found", "message": "Assessment attempt was not found."},
        ) from exc
    except AssessmentAttemptAlreadySubmitted as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "attempt_already_submitted",
                "message": "This attempt is immutable and has already been submitted with different answers.",
            },
        ) from exc
    except InvalidAssessmentAnswer as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_assessment_submission", "message": str(exc)},
        ) from exc
