"use client";

import type { ConceptDefinition } from "@/lib/progress";
import { AssessmentPanel } from "@/components/assessment-panel";
import { PracticePanel } from "@/components/practice-panel";
import { ProgressPanel, ProgressProvider, useLessonProgress } from "@/components/progress-provider";

function LearningActivities({ lessonId, concepts }: { lessonId: string; concepts: ConceptDefinition[] }) {
  const { recordPractice, recordAssessment } = useLessonProgress();
  return (
    <>
      <PracticePanel lessonId={lessonId} onValidatedOutcome={(practice, exercise, correct) => recordPractice(practice, exercise.exercise_id, exercise.concept_id, correct)} />
      <AssessmentPanel lessonId={lessonId} onValidatedResult={recordAssessment} />
      <ProgressPanel lessonId={lessonId} concepts={concepts} />
    </>
  );
}

export function LessonLearningExperience({ lessonId, concepts }: { lessonId: string; concepts: ConceptDefinition[] }) {
  return <ProgressProvider lessonId={lessonId} concepts={concepts}><LearningActivities lessonId={lessonId} concepts={concepts} /></ProgressProvider>;
}
