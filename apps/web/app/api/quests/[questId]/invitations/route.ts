import { proxyBackendRequest } from "@/lib/backend-proxy";
export async function POST(request: Request, { params }: { params: Promise<{ questId: string }> }) {
  const { questId } = await params;
  return proxyBackendRequest(`/api/quests/${encodeURIComponent(questId)}/invitations`, request);
}
export async function DELETE(request: Request, { params }: { params: Promise<{ questId: string }> }) {
  const { questId } = await params;
  return proxyBackendRequest(`/api/quests/${encodeURIComponent(questId)}/invitations`, request);
}
