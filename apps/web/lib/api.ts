export type CourseModule = {
  id: string;
  title: string;
  description: string;
};

export type CourseLevel = {
  id: string;
  label: string;
  title: string;
  description: string;
  modules: CourseModule[];
};

export type CourseSummary = {
  id: string;
  slug: string;
  title: string;
  description: string;
  learning_rationale: string;
  curriculum_note: string;
  level_count: number;
  module_count: number;
};

export type CourseDetail = CourseSummary & {
  levels: CourseLevel[];
};

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiFetch(path: string): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
}

export async function getCourses(): Promise<CourseSummary[]> {
  const response = await apiFetch("/api/courses");
  if (!response.ok) {
    throw new Error(`Course catalog request failed (${response.status}).`);
  }
  return (await response.json()) as CourseSummary[];
}

export async function getCourse(slug: string): Promise<CourseDetail | null> {
  const response = await apiFetch(`/api/courses/${encodeURIComponent(slug)}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Course request failed (${response.status}).`);
  }
  return (await response.json()) as CourseDetail;
}
