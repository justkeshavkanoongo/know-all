import { proxyBackendRequest } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ questId: string; sectionId: string }> },
) {
  const { questId, sectionId } = await params;
  return proxyBackendRequest(
    `/api/quests/${encodeURIComponent(questId)}/artifact/sections/${encodeURIComponent(sectionId)}`,
    request,
  );
}
