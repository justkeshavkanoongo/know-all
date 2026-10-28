"use client";

import { useCallback, useEffect, useState } from "react";

import { PracticePanel } from "@/components/practice-panel";

type MemberStatus = { role: "host" | "collaborator"; checked_count: number; evidence_ids: string[]; required_count: 7; complete: boolean };
type Preparation = { quest_id: string; current_role: "host" | "collaborator"; state: string; members: MemberStatus[] };
type Snapshot = {
  explanation: string;
  example: string;
  misconception_correction: { misconception: string; correction: string };
  follow_up_question: string;
};
type Revision = {
  revision_number: number;
  changed_section: string | null;
  author_role: "host" | "collaborator" | "system";
  created_at: string;
  snapshot: Snapshot;
};
type Artifact = { quest_id: string; current_revision: number; snapshot: Snapshot; revisions: Revision[]; history_truncated: boolean };
type Section = "explanation" | "example" | "misconception_correction" | "follow_up_question";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store", headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  const data = await response.json().catch(() => ({})) as T & { message?: string; current_revision?: number };
  if (!response.ok) {
    const error = new Error(data.message ?? `Request failed (${response.status}).`);
    Object.assign(error, { status: response.status, currentRevision: data.current_revision });
    throw error;
  }
  return data;
}

export function QuestPreparation({ questId, onQuestChanged }: { questId: string; onQuestChanged: () => void }) {
  const [status, setStatus] = useState<Preparation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await requestJson<Preparation>(`/api/quests/${encodeURIComponent(questId)}/preparation`);
      setStatus(next);
      if (next.state === "collaborating") onQuestChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preparation status could not be loaded.");
    } finally { setLoading(false); }
  }, [questId, onQuestChanged]);

  useEffect(() => { void refresh(); }, [refresh]);
  const own = status?.members.find((member) => member.role === status.current_role);
  const other = status?.members.find((member) => member.role !== status.current_role);

  return <section className="mt-6 rounded-2xl border border-line bg-surface p-5 sm:p-7" aria-labelledby="preparation-status-heading">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="eyebrow">Before you work together</p><h2 id="preparation-status-heading" className="mt-2 font-display text-2xl font-medium text-ink">Prepare independently</h2></div>
      <button type="button" onClick={() => { void refresh(); }} disabled={loading} className="rounded-sm border border-line px-3 py-2 text-sm font-semibold text-navy hover:border-sage focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{loading ? "Refreshing…" : "Refresh status"}</button>
    </div>
    <p className="mt-3 text-sm leading-6 text-muted">Both members need seven distinct correct answers from the reviewed lesson practice. This verifies answers for each quest session; it does not prove distinct human identities or formal mastery.</p>
    {error && <p className="mt-4 text-sm text-red-800" role="alert">{error}</p>}
    {status && <ul className="mt-5 grid gap-3 sm:grid-cols-2" aria-live="polite">{status.members.map((member) => <li key={member.role} className="rounded-xl border border-line bg-paper p-4">
      <p className="font-semibold text-ink">{member.role === status.current_role ? "You" : "Your partner"} · {member.complete ? "Ready" : "Preparing"}</p>
      <p className="mt-1 text-sm text-muted">{member.checked_count} of {member.required_count} distinct exercises checked</p>
    </li>)}</ul>}
    {status?.state === "awaiting_partner" && <p className="mt-5 text-sm leading-6 text-muted" role="status">Preparation opens after your partner joins.</p>}
    {status?.state === "preparing" && own && !own.complete && <PracticePanel
      lessonId="german-a1-greetings" questId={questId}
      completedEvidenceIds={own.evidence_ids}
      onQuestEvidence={() => { void refresh(); }}
    />}
    {status?.state === "preparing" && own?.complete && <p className="mt-5 rounded-xl bg-paper p-4 text-sm leading-6 text-muted" role="status">Your preparation is complete. Refresh this status after your partner finishes.</p>}
    {status?.state === "collaborating" && <p className="mt-5 rounded-xl bg-paper p-4 text-sm leading-6 text-muted" role="status">Both members are ready. The shared artifact is now open below.</p>}
    {status?.state === "expired" && <p className="mt-5 text-sm text-muted" role="status">This quest has expired and can no longer accept preparation.</p>}
  </section>;
}

function snapshotDraft(snapshot: Snapshot) {
  return {
    explanation: snapshot.explanation,
    example: snapshot.example,
    misconception: snapshot.misconception_correction.misconception,
    correction: snapshot.misconception_correction.correction,
    follow_up_question: snapshot.follow_up_question,
  };
}

export function QuestArtifactWorkspace({ questId }: { questId: string }) {
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [draft, setDraft] = useState<ReturnType<typeof snapshotDraft> | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<Section | null>(null);
  const [message, setMessage] = useState("");
  const [messageRole, setMessageRole] = useState<"status" | "alert">("status");

  const refresh = useCallback(async (preserveDraft = false) => {
    setLoading(true);
    try {
      const next = await requestJson<Artifact>(`/api/quests/${encodeURIComponent(questId)}/artifact`);
      setArtifact(next);
      if (!preserveDraft) setDraft(snapshotDraft(next.snapshot));
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "The artifact could not be loaded.");
      setMessageRole("alert");
    } finally { setLoading(false); }
  }, [questId]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function save(section: Section) {
    if (!artifact || !draft) return;
    setSaving(section);
    setMessage("Saving your contribution…");
    setMessageRole("status");
    const content = section === "misconception_correction"
      ? { misconception: draft.misconception, correction: draft.correction }
      : draft[section];
    try {
      await requestJson<Revision>(`/api/quests/${encodeURIComponent(questId)}/artifact/sections/${section}`, {
        method: "PATCH",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ expected_revision: artifact.current_revision, content }),
      });
      setMessage("Contribution saved.");
      setMessageRole("status");
      await refresh();
    } catch (cause) {
      const conflict = typeof cause === "object" && cause !== null && "status" in cause && cause.status === 409;
      if (conflict) {
        setMessage("Someone saved a newer revision. The latest artifact has been loaded; your text is preserved above so you can reconcile it before saving again.");
        setMessageRole("alert");
        await refresh(true);
      } else {
        setMessage(cause instanceof Error ? `${cause.message} Your draft is still available; retry when ready.` : "Save failed. Your draft is still available.");
        setMessageRole("alert");
      }
    } finally { setSaving(null); }
  }

  const contributors = new Set(artifact?.revisions.map((revision) => revision.author_role).filter((role) => role !== "system") ?? []);
  const textField = (section: "explanation" | "example" | "follow_up_question", label: string, help: string, maxLength: number) => (
    <label className="mt-5 block text-sm font-semibold text-ink">{label}<span className="mt-1 block font-normal leading-6 text-muted">{help}</span>
      <textarea maxLength={maxLength} rows={section === "explanation" ? 4 : 3} value={draft?.[section] ?? ""} onChange={(event) => setDraft((current) => current ? { ...current, [section]: event.target.value } : current)} className="mt-2 w-full rounded-lg border border-line bg-white p-3 text-base font-normal leading-6 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" />
      <span className="mt-1 block text-xs font-normal text-muted">{draft?.[section].length ?? 0}/{maxLength}</span>
    </label>
  );

  return <section className="mt-6 rounded-2xl border border-line bg-surface p-5 sm:p-7" aria-labelledby="artifact-heading">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow">Shared learning artifact</p><h2 id="artifact-heading" className="mt-2 font-display text-2xl font-medium text-ink">Build a concept guide together</h2></div>
      <button type="button" onClick={() => { setMessage(""); void refresh(); }} disabled={loading || saving !== null} className="rounded-sm border border-line px-3 py-2 text-sm font-semibold text-navy hover:border-sage focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{loading ? "Refreshing…" : "Refresh artifact"}</button></div>
    <p className="mt-3 text-sm leading-6 text-muted">Edits create numbered snapshots. Refresh to see your partner’s latest work; no live presence is shown.</p>
    {message && <p className="mt-4 rounded-lg bg-paper p-3 text-sm leading-6 text-ink" role={messageRole} aria-live="polite">{message}</p>}
    {loading && !artifact && <p className="mt-5 text-sm text-muted" role="status">Loading shared artifact…</p>}
    {artifact && draft && <>
      <p className="mt-5 text-sm font-semibold text-navy">Current revision {artifact.current_revision}</p>
      <div className="mt-3 flex flex-wrap gap-2" aria-label="Contribution status">{(["host", "collaborator"] as const).map((role) => <span key={role} className="rounded-full bg-paper px-3 py-1.5 text-xs font-semibold text-navy">{role === "host" ? "Host" : "Collaborator"}: {contributors.has(role) ? "contributed" : "has not contributed yet"}</span>)}</div>
      <form onSubmit={(event) => event.preventDefault()}>
        {textField("explanation", "1. Explain the concept", "Use your own words.", 2000)}
        <button type="button" disabled={saving !== null} onClick={() => void save("explanation")} className="mt-2 rounded-sm bg-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{saving === "explanation" ? "Saving…" : "Save explanation"}</button>
        {textField("example", "2. Give a relevant example", "Make the idea concrete.", 2000)}
        <button type="button" disabled={saving !== null} onClick={() => void save("example")} className="mt-2 rounded-sm bg-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{saving === "example" ? "Saving…" : "Save example"}</button>
        <fieldset className="mt-6 border-t border-line pt-5">
          <legend className="text-sm font-semibold text-ink">3. Describe a misconception and correct it</legend>
          <label className="mt-3 block text-sm font-semibold text-ink">Misconception<textarea maxLength={1200} rows={2} value={draft.misconception} onChange={(event) => setDraft((current) => current ? { ...current, misconception: event.target.value } : current)} className="mt-2 w-full rounded-lg border border-line bg-white p-3 font-normal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" /></label>
          <label className="mt-3 block text-sm font-semibold text-ink">Correction<textarea maxLength={1200} rows={2} value={draft.correction} onChange={(event) => setDraft((current) => current ? { ...current, correction: event.target.value } : current)} className="mt-2 w-full rounded-lg border border-line bg-white p-3 font-normal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" /></label>
          <button type="button" disabled={saving !== null} onClick={() => void save("misconception_correction")} className="mt-2 rounded-sm bg-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{saving === "misconception_correction" ? "Saving…" : "Save correction"}</button>
        </fieldset>
        {textField("follow_up_question", "4. Ask a follow-up question", "Leave a question that invites further thought.", 1000)}
        <button type="button" disabled={saving !== null} onClick={() => void save("follow_up_question")} className="mt-2 rounded-sm bg-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{saving === "follow_up_question" ? "Saving…" : "Save question"}</button>
      </form>
      <section className="mt-8 border-t border-line pt-6" aria-labelledby="revision-history-heading">
        <h3 id="revision-history-heading" className="font-display text-xl font-medium text-ink">Revision history</h3>
        {artifact.history_truncated && <p className="mt-2 text-sm text-muted">Showing the latest 50 revisions.</p>}
        <ol className="mt-4 space-y-3">{[...artifact.revisions].reverse().map((revision) => <li key={revision.revision_number} className="rounded-xl border border-line p-4">
          <details><summary className="cursor-pointer text-sm font-semibold text-navy focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage">Revision {revision.revision_number} · {revision.author_role === "system" ? "Initial draft" : revision.author_role === "host" ? "Host" : "Collaborator"}{revision.changed_section ? ` · ${revision.changed_section.replaceAll("_", " ")}` : ""} · {new Date(revision.created_at).toLocaleString()}</summary>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-5 text-muted">{JSON.stringify(revision.snapshot, null, 2)}</pre>
          </details>
        </li>)}</ol>
      </section>
    </>}
  </section>;
}
