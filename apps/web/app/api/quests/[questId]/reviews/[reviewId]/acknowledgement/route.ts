import { proxyBackendRequest } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ questId: string; reviewId: string }> },
) {
  const { questId, reviewId } = await params;
  return proxyBackendRequest(
    `/api/quests/${encodeURIComponent(questId)}/reviews/${encodeURIComponent(reviewId)}/acknowledgement`,
    request,
  );
}
