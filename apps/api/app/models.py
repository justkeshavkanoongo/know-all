from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field


class ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: str


class CourseModule(ApiModel):
    id: str
    title: str
    description: str


class CourseLevel(ApiModel):
    id: str
    label: str
    title: str
    description: str
    modules: tuple[CourseModule, ...]


class CourseBase(ApiModel):
    id: str
    slug: str
    title: str
    description: str
    learning_rationale: str
    curriculum_note: str


class CourseSummary(CourseBase):
    level_count: int
    module_count: int


class CourseDetail(CourseBase):
    levels: tuple[CourseLevel, ...]

    @computed_field
    @property
    def level_count(self) -> int:
        return len(self.levels)

    @computed_field
    @property
    def module_count(self) -> int:
        return sum(len(level.modules) for level in self.levels)


class ApiError(ApiModel):
    code: str
    message: str
