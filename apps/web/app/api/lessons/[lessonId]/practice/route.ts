import { proxyBackendRequest } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ lessonId: string }> },
) {
  const { lessonId } = await params;
  return proxyBackendRequest(`/api/lessons/${encodeURIComponent(lessonId)}/practice`);
}
