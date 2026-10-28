import { proxyBackendRequest } from "@/lib/backend-proxy";
export async function GET(request: Request, { params }: { params: Promise<{ questId: string }> }) {
  const { questId } = await params;
  return proxyBackendRequest(`/api/quests/${encodeURIComponent(questId)}`, request);
}
