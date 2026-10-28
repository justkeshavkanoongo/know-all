import { proxyBackendRequest } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ lessonId: string; attemptId: string }> },
) {
  const { lessonId, attemptId } = await params;
  return proxyBackendRequest(
    `/api/lessons/${encodeURIComponent(lessonId)}/assessment-attempts/${encodeURIComponent(attemptId)}/submit`,
    request,
  );
}
