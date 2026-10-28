from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .catalog import get_course_by_slug, list_course_summaries
from .models import ApiError, CourseDetail, CourseSummary, HealthResponse

app = FastAPI(
    title="Know It All API",
    version="1.0.0",
    description="A small, typed API for the Know It All course catalog.",
)


@app.exception_handler(StarletteHTTPException)
async def predictable_http_errors(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        error = ApiError.model_validate(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=error.model_dump())
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
