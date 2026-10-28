from typing import Literal

from pydantic import computed_field

from .models import ApiModel


class LessonCourseReference(ApiModel):
    id: str
    slug: str
    title: str


class LessonLevelReference(ApiModel):
    id: str
    title: str


class LessonObjective(ApiModel):
    id: str
    description: str


class LessonVocabulary(ApiModel):
    term: str
    translation: str
    example: str
    example_translation: str
    pronunciation_note: str | None = None


class LessonGrammar(ApiModel):
    id: str
    title: str
    explanation: str
    examples: tuple[str, ...]


class LessonStep(ApiModel):
    title: str
    explanation: str
    example: str


class LessonSection(ApiModel):
    section_id: str
    title: str
    introduction: str
    steps: tuple[LessonStep, ...]


class DialogueTurn(ApiModel):
    speaker: str
    text: str
    translation: str


class LessonDialogue(ApiModel):
    dialogue_id: str
    title: str
    context: str
    turns: tuple[DialogueTurn, ...]


class CommonMistake(ApiModel):
    incorrect: str
    correction: str
    explanation: str


class LessonConcept(ApiModel):
    id: str
    title: str
    description: str


class LessonDetail(ApiModel):
    lesson_id: str
    course: LessonCourseReference
    level: LessonLevelReference
    title: str
    review_status: Literal["reviewed"]
    content_version: str
    objectives: tuple[LessonObjective, ...]
    vocabulary: tuple[LessonVocabulary, ...]
    grammar: tuple[LessonGrammar, ...]
    sections: tuple[LessonSection, ...]
    dialogues: tuple[LessonDialogue, ...]
    common_mistakes: tuple[CommonMistake, ...]
    recap: tuple[str, ...]
    concepts: tuple[LessonConcept, ...]

    @computed_field
    @property
    def concept_ids(self) -> tuple[str, ...]:
        return tuple(concept.id for concept in self.concepts)
