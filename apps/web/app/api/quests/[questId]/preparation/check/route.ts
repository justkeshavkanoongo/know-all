import { proxyBackendRequest } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: Request, { params }: { params: Promise<{ questId: string }> }) {
  const { questId } = await params;
  return proxyBackendRequest(`/api/quests/${encodeURIComponent(questId)}/preparation/check`, request);
}
