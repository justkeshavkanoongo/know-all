import { proxyBackendRequest } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ questId: string }> }) {
  const { questId } = await params;
  return proxyBackendRequest(`/api/quests/${encodeURIComponent(questId)}/artifact`, request);
}
