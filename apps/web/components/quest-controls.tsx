"use client";

import { useCallback, useEffect, useState } from "react";
import { QuestArtifactWorkspace, QuestPreparation } from "@/components/quest-learning";
import { QuestReviewWorkspace } from "@/components/quest-review";

type Quest = { quest_id: string; state: string; lesson_id: string; participant_count: number; expires_at: string; version: number };
type ApiError = { message?: string };

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  const data = await response.json().catch(() => ({})) as T & ApiError;
  if (!response.ok) throw new Error(data.message ?? `Request failed (${response.status}).`);
  return data;
}

export function StartQuestButton() {
  const [adult, setAdult] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true); setError("");
    try {
      await jsonRequest("/api/guest-sessions", { method: "POST", body: JSON.stringify({ confirm_adult: true }) });
      const quest = await jsonRequest<Quest>("/api/quests", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ lesson_id: "german-a1-greetings", concept_ids: ["german-greetings"], template_id: "concept-guide-v1" }) });
      window.location.assign(`/quests/${quest.quest_id}`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The quest could not be created."); setBusy(false); }
  }
  return <section className="mt-8 rounded-2xl border border-line bg-surface p-5 sm:p-7" aria-labelledby="quest-start-title">
    <p className="eyebrow">Learn together</p><h2 id="quest-start-title" className="mt-2 font-display text-2xl font-medium text-ink">Start a private quest</h2>
    <p className="mt-2 text-sm leading-6 text-muted">Invite one person to explore German greetings with you. Participation is pseudonymous; anyone with an unused invitation can claim it.</p>
    <label className="mt-4 flex items-start gap-3 text-sm leading-6 text-ink"><input type="checkbox" checked={adult} onChange={(event) => setAdult(event.target.checked)} className="mt-1 accent-sage" />I confirm that I am 18 or older.</label>
    <button type="button" disabled={!adult || busy} onClick={start} className="mt-4 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Creating quest…" : "Create private quest"}</button>
    {error && <p role="alert" className="mt-3 text-sm text-red-800">{error}</p>}
  </section>;
}

export function QuestStatus({ questId }: { questId: string }) {
  const [quest, setQuest] = useState<Quest | null>(null);
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const refresh = useCallback(async () => {
    try { setQuest(await jsonRequest<Quest>(`/api/quests/${encodeURIComponent(questId)}`)); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Quest unavailable."); }
  }, [questId]);
  const refreshQuest = useCallback(() => { void refresh(); }, [refresh]);
  useEffect(() => { void refresh(); }, [refresh]);
  async function invite() {
    setBusy(true); setMessage("");
    try {
      const result = await jsonRequest<{ invitation_token: string | null; expires_at: string; status: string }>(`/api/quests/${encodeURIComponent(questId)}/invitations`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } });
      if (!result.invitation_token) throw new Error("An invitation was already issued for that request. Create a fresh invitation to rotate it.");
      const url = new URL("/quests/join", window.location.origin); url.hash = new URLSearchParams({ token: result.invitation_token }).toString();
      setLink(url.toString()); setMessage(`Invitation expires ${new Date(result.expires_at).toLocaleString()}.`);
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "Invitation could not be created."); }
    finally { setBusy(false); }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(link); setMessage("Invitation link copied."); }
    catch { setMessage("Copy was blocked. Select and copy the invitation link below."); }
  }
  async function revoke() {
    setBusy(true);
    try { await jsonRequest(`/api/quests/${encodeURIComponent(questId)}/invitations`, { method: "DELETE" }); setLink(""); setMessage("Any unused invitation has been revoked."); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Invitation could not be revoked."); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto min-h-[70vh] max-w-3xl px-5 py-12 sm:px-8 sm:py-20">
    <a href="/lessons/german-a1-greetings" className="text-sm font-semibold underline decoration-sage underline-offset-4">← Return to lesson</a>
    <p className="eyebrow mt-10">Private learning quest</p><h1 className="mt-3 font-display text-4xl font-medium tracking-[-0.035em] text-navy">Your German greetings quest</h1>
    {!quest && !message && <p className="mt-6 text-muted" role="status">Loading quest…</p>}
    {quest && <section className="mt-8 rounded-2xl border border-line bg-surface p-6" aria-live="polite"><p className="font-semibold text-ink">{quest.state === "awaiting_partner" ? "Waiting for a partner" : "A partner joined"}</p><p className="mt-2 text-sm leading-6 text-muted">{quest.participant_count} of 2 participants · expires {new Date(quest.expires_at).toLocaleString()}</p>
      {quest.state === "awaiting_partner" && <><button disabled={busy} onClick={invite} className="mt-5 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Working…" : link ? "Create a fresh invitation" : "Create invitation link"}</button>{link && <><label className="mt-4 block text-sm font-semibold" htmlFor="invite-link">Invitation link</label><input id="invite-link" readOnly value={link} className="mt-2 w-full rounded-lg border border-line bg-paper px-3 py-3 text-sm"/><button onClick={copy} className="mt-3 mr-4 rounded-full border border-line px-4 py-2 text-sm font-semibold">Copy link</button><button onClick={revoke} className="mt-3 rounded-full border border-line px-4 py-2 text-sm font-semibold">Revoke link</button></>}</>}
      {(quest.state === "preparing" || quest.state === "collaborating") && <QuestPreparation questId={questId} onQuestChanged={refreshQuest} />}
      {quest.state === "collaborating" && <QuestArtifactWorkspace questId={questId} />}
      {(quest.state === "collaborating" || quest.state === "expired") && <QuestReviewWorkspace questId={questId} />}
      {(quest.state === "expired" || quest.state === "cancelled") && <p className="mt-4 text-sm text-muted" role="status">This quest is {quest.state} and can no longer be changed.</p>}
    </section>}
    {message && <p role="status" className="mt-4 text-sm text-muted">{message}</p>}
  </main>;
}

export function InvitationJoin() {
  const [token, setToken] = useState("");
  const [adult, setAdult] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Checking invitation…");
  const [redeemKey, setRedeemKey] = useState("");
  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    window.history.replaceState(null, "", window.location.pathname);
    setToken(value); setMessage(value ? "Review the participation note, then confirm your age to join." : "Invitation is missing or invalid.");
  }, []);
  async function join() {
    setBusy(true); setMessage("");
    try {
      const key = redeemKey || crypto.randomUUID();
      setRedeemKey(key);
      const quest = await jsonRequest<Quest>("/api/quest-invitations/redeem", { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify({ token, confirm_adult: true }) });
      window.location.assign(`/quests/${quest.quest_id}`);
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "Invitation is invalid, expired, revoked, or already used."); setBusy(false); }
  }
  return <main className="mx-auto min-h-[70vh] max-w-2xl px-5 py-12 sm:px-8 sm:py-20"><p className="eyebrow">Invitation</p><h1 className="mt-3 font-display text-4xl font-medium text-navy">Join a private learning quest</h1><p className="mt-5 leading-7 text-muted">You will join pseudonymously using this browser. The host can see that a second participant joined; this phase does not collect a name, email, or profile.</p>
    <label className="mt-6 flex items-start gap-3 text-sm leading-6 text-ink"><input type="checkbox" checked={adult} onChange={(event) => setAdult(event.target.checked)} className="mt-1 accent-sage"/>I confirm that I am 18 or older.</label>
    <button disabled={!token || !adult || busy} onClick={join} className="mt-5 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Joining…" : "Join quest"}</button>
    <p role="status" className="mt-4 text-sm text-muted">{message}</p></main>;
}
