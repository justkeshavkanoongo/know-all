import { InvitationJoin } from "@/components/quest-controls";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "Join a private quest", referrer: "no-referrer" };
export default function JoinQuestPage() { return <InvitationJoin />; }
