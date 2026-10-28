import { QuestStatus } from "@/components/quest-controls";
export default async function QuestPage({ params }: { params: Promise<{ questId: string }> }) {
  const { questId } = await params;
  return <QuestStatus questId={questId} />;
}
