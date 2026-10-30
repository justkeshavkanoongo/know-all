"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Rating = "needs_work" | "mostly_there" | "clear";
type Snapshot = {
  explanation: string;
  example: string;
  misconception_correction: { misconception: string; correction: string };
  follow_up_question: string;
};
type Review = {
  review_id: string;
  review_round: 1;
  revision_id: string;
  revision_number: number;
  revision_is_current: boolean;
  reviewer_role: "host" | "collaborator";
  recipient_role: "host" | "collaborator";
  rubric_version: "peer-review-v1";
  conceptual_correctness: Rating;
  explanation_clarity: Rating;
  example_relevance: Rating;
  misconception_correction: Rating;
  follow_up_usefulness: Rating;
  strength: string;
  improvement_suggestion: string;
  rationale: string;
  created_at: string;
  acknowledged_at: string | null;
  response_text: string | null;
  responded_at: string | null;
  snapshot: Snapshot;
};
type ReviewableRevision = { revision_id: string; revision_number: number; author_role: "host" | "collaborator"; created_at: string; snapshot: Snapshot };
type Status = {
  quest_id: string;
  current_role: "host" | "collaborator";
  state: "awaiting_partner" | "preparing" | "collaborating" | "expired" | "cancelled";
  eligible: boolean;
  submitted_by_you: boolean;
  submitted_by_partner: boolean;
  reviewable_revision: ReviewableRevision | null;
  review_given: Review | null;
  review_received: Review | null;
};
type ReviewPayload = {
  revision_id: string;
  rubric_version: "peer-review-v1";
  conceptual_correctness: Rating | "";
  explanation_clarity: Rating | "";
  example_relevance: Rating | "";
  misconception_correction: Rating | "";
  follow_up_usefulness: Rating | "";
  strength: string;
  improvement_suggestion: string;
  rationale: string;
};
type ApiError = { message?: string };

const criteria = [
  ["conceptual_correctness", "Conceptual correctness", "Does the explanation get the idea right?"],
  ["explanation_clarity", "Explanation clarity", "Could another learner understand it?"],
  ["example_relevance", "Example relevance", "Does the example show the idea in use?"],
  ["misconception_correction", "Misconception and correction", "Is the misconception plausible and the correction accurate?"],
  ["follow_up_usefulness", "Follow-up usefulness", "Would the question help someone think or practise?"],
] as const;
const ratingLabels: Record<Rating, string> = { needs_work: "Needs work", mostly_there: "Mostly there", clear: "Clear" };

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store", headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  const data = await response.json().catch(() => ({})) as T & ApiError;
  if (!response.ok) throw new Error(data.message ?? `Request failed (${response.status}).`);
  return data;
}

function SnapshotView({ snapshot }: { snapshot: Snapshot }) {
  const rows = [
    ["Explanation", snapshot.explanation],
    ["Example", snapshot.example],
    ["Misconception", snapshot.misconception_correction.misconception],
    ["Correction", snapshot.misconception_correction.correction],
    ["Follow-up question", snapshot.follow_up_question],
  ];
  return <dl className="mt-4 grid gap-3 rounded-xl bg-paper p-4 sm:grid-cols-2">{rows.map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{value || "Not filled in yet."}</dd></div>)}</dl>;
}

function ReviewCard({ review, title }: { review: Review; title: string }) {
  const scores: [string, Rating][] = [
    ["Conceptual correctness", review.conceptual_correctness],
    ["Explanation clarity", review.explanation_clarity],
    ["Example relevance", review.example_relevance],
    ["Misconception and correction", review.misconception_correction],
    ["Follow-up usefulness", review.follow_up_usefulness],
  ];
  return <article className="mt-5 rounded-xl border border-line p-4 sm:p-5" aria-label={title}>
    <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="font-semibold text-ink">{title}</h3><p className="text-xs text-muted">Revision {review.revision_number} · {new Date(review.created_at).toLocaleString()}</p></div>
    {!review.revision_is_current && <p className="mt-3 rounded-lg bg-paper p-3 text-sm leading-6 text-muted" role="note">This feedback is for revision {review.revision_number}. The artifact has since changed; this review remains attached to the snapshot shown below.</p>}
    <SnapshotView snapshot={review.snapshot} />
    <dl className="mt-4 grid gap-2 sm:grid-cols-2">{scores.map(([label, rating]) => <div key={label} className="flex flex-wrap justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm"><dt className="text-muted">{label}</dt><dd className="font-semibold text-navy">{ratingLabels[rating]}</dd></div>)}</dl>
    <dl className="mt-4 space-y-3 text-sm leading-6"><div><dt className="font-semibold text-ink">A strength</dt><dd className="mt-1 whitespace-pre-wrap break-words text-muted">{review.strength}</dd></div><div><dt className="font-semibold text-ink">One improvement</dt><dd className="mt-1 whitespace-pre-wrap break-words text-muted">{review.improvement_suggestion}</dd></div><div><dt className="font-semibold text-ink">Why these ratings?</dt><dd className="mt-1 whitespace-pre-wrap break-words text-muted">{review.rationale}</dd></div></dl>
    {review.acknowledged_at && <p className="mt-4 text-xs text-muted">Recipient acknowledged {new Date(review.acknowledged_at).toLocaleString()}.</p>}
    {review.response_text && <p className="mt-3 rounded-lg bg-paper p-3 text-sm leading-6 text-ink"><span className="font-semibold">Recipient response:</span> {review.response_text}</p>}
  </article>;
}

export function QuestReviewWorkspace({ questId }: { questId: string }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [responseText, setResponseText] = useState("");
  const [payload, setPayload] = useState<ReviewPayload>({
    revision_id: "", rubric_version: "peer-review-v1",
    conceptual_correctness: "", explanation_clarity: "", example_relevance: "",
    misconception_correction: "", follow_up_usefulness: "",
    strength: "", improvement_suggestion: "", rationale: "",
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await requestJson<Status>(`/api/quests/${encodeURIComponent(questId)}/reviews`);
      setStatus(next);
      if (next.reviewable_revision) setPayload((current) => {
        if (current.revision_id === next.reviewable_revision?.revision_id) return current;
        return {
          revision_id: next.reviewable_revision?.revision_id ?? "", rubric_version: "peer-review-v1",
          conceptual_correctness: "", explanation_clarity: "", example_relevance: "",
          misconception_correction: "", follow_up_usefulness: "",
          strength: "", improvement_suggestion: "", rationale: "",
        };
      });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Peer feedback could not be loaded."); }
    finally { setLoading(false); }
  }, [questId]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!status?.reviewable_revision) return;
    setSubmitting(true); setError(""); setNotice("");
    try {
      await requestJson<Review>(`/api/quests/${encodeURIComponent(questId)}/reviews`, {
        method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(payload),
      });
      setNotice("Your review was submitted. Your partner can see it now.");
      await refresh();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Your review could not be submitted. Refresh and try again.";
      await refresh();
      setError(message);
    }
    finally { setSubmitting(false); }
  }

  async function acknowledge(reviewId: string) {
    setActionBusy(true); setError(""); setNotice("");
    try {
      await requestJson(`/api/quests/${encodeURIComponent(questId)}/reviews/${encodeURIComponent(reviewId)}/acknowledgement`, {
        method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: "{}",
      });
      setNotice("Feedback acknowledged."); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Acknowledgement could not be saved."); }
    finally { setActionBusy(false); }
  }

  async function respond(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!status?.review_received) return;
    setActionBusy(true); setError(""); setNotice("");
    try {
      await requestJson(`/api/quests/${encodeURIComponent(questId)}/reviews/${encodeURIComponent(status.review_received.review_id)}/response`, {
        method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ response: responseText }),
      });
      setNotice("Your response was shared with your partner."); setResponseText(""); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Your response could not be saved."); }
    finally { setActionBusy(false); }
  }

  const field = (name: "strength" | "improvement_suggestion" | "rationale", label: string, hint: string) => (
    <label className="mt-4 block text-sm font-semibold text-ink">{label}<span className="mt-1 block font-normal leading-6 text-muted">{hint}</span>
      <textarea required minLength={1} maxLength={500} rows={3} value={payload[name]} onChange={(event) => setPayload((current) => ({ ...current, [name]: event.target.value }))} className="mt-2 w-full rounded-lg border border-line bg-white p-3 text-base font-normal leading-6 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" />
      <span className="mt-1 block text-xs font-normal text-muted">{payload[name].length}/500</span>
    </label>
  );

  return <section className="mt-6 rounded-2xl border border-line bg-surface p-5 sm:p-7" aria-labelledby="peer-review-heading">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow">Learn from each other</p><h2 id="peer-review-heading" className="mt-2 font-display text-2xl font-medium text-ink">Peer review</h2></div>
      <button type="button" onClick={() => { void refresh(); }} disabled={loading || submitting || actionBusy} className="rounded-sm border border-line px-3 py-2 text-sm font-semibold text-navy hover:border-sage focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{loading ? "Refreshing…" : "Refresh reviews"}</button></div>
    <p className="mt-3 text-sm leading-6 text-muted">Give your partner clear, kind feedback on one exact artifact revision. Ratings are guidance, not a grade or proof of mastery. Your partner can see your review as soon as you submit it.</p>
    {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm leading-6 text-red-900" role="alert">{error}</p>}
    {notice && <p className="mt-4 rounded-lg bg-paper p-3 text-sm leading-6 text-ink" role="status" aria-live="polite">{notice}</p>}
    {loading && !status && <p className="mt-4 text-sm text-muted" role="status">Loading peer review…</p>}
    {status && <>
      {(status.state === "awaiting_partner" || status.state === "preparing") && <p className="mt-5 rounded-xl bg-paper p-4 text-sm leading-6 text-muted" role="status">Peer review opens after both participants have prepared and contributed to the shared artifact.</p>}
      {status.state === "expired" && <p className="mt-3 text-sm text-muted" role="status">This quest has expired. Existing feedback remains available to its members.</p>}
      {status.eligible && !status.submitted_by_you && status.reviewable_revision && <div className="mt-5 border-t border-line pt-5">
        <p className="text-sm font-semibold text-navy">Your first-round review · {status.reviewable_revision.author_role === "host" ? "Host" : "Collaborator"} contribution · revision {status.reviewable_revision.revision_number}</p>
        <SnapshotView snapshot={status.reviewable_revision.snapshot} />
        <form onSubmit={submit} className="mt-5" aria-label="Submit your peer review">
          {criteria.map(([name, title, question], index) => <fieldset key={name} className="mt-5 rounded-xl border border-line p-4"><legend className="px-1 text-sm font-semibold text-ink">{index + 1}. {title}</legend><p className="mt-1 text-sm leading-6 text-muted">{question}</p><div className="mt-3 flex flex-wrap gap-4">{(["needs_work", "mostly_there", "clear"] as const).map((rating) => <label key={rating} className="inline-flex items-center gap-2 text-sm text-ink"><input required type="radio" name={name} value={rating} checked={payload[name] === rating} onChange={() => setPayload((current) => ({ ...current, [name]: rating }))} className="accent-sage focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" />{ratingLabels[rating]}</label>)}</div></fieldset>)}
          {field("strength", "One specific strength", "Name something concrete that works well.")}
          {field("improvement_suggestion", "One actionable improvement", "Suggest one change your partner could make.")}
          {field("rationale", "Why did you choose these ratings?", "Briefly explain what in the revision informed your assessment.")}
          <button type="submit" disabled={submitting || !payload.conceptual_correctness || !payload.explanation_clarity || !payload.example_relevance || !payload.misconception_correction || !payload.follow_up_usefulness} className="mt-5 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{submitting ? "Submitting review…" : "Submit first-round review"}</button>
        </form>
      </div>}
      {status.eligible && status.submitted_by_you && !status.submitted_by_partner && <p className="mt-5 rounded-xl bg-paper p-4 text-sm leading-6 text-muted" role="status">Your first-round review is submitted. You’re waiting for your partner to review your contribution. Later revisions do not create another required review round.</p>}
      {status.review_given && <ReviewCard review={status.review_given} title="Your review" />}
      {status.review_received && <div className="mt-5 border-t border-line pt-5"><ReviewCard review={status.review_received} title="Feedback from your partner" />
        {status.state === "collaborating" && !status.review_received.acknowledged_at && <button type="button" disabled={actionBusy} onClick={() => void acknowledge(status.review_received!.review_id)} className="mt-4 rounded-full border border-line px-4 py-2.5 text-sm font-semibold text-navy focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{actionBusy ? "Saving…" : "Acknowledge feedback"}</button>}
        {status.review_received.acknowledged_at && <p className="mt-4 text-sm text-muted" role="status">Feedback acknowledged {new Date(status.review_received.acknowledged_at).toLocaleString()}.</p>}
        {status.state === "collaborating" && status.review_received.acknowledged_at && !status.review_received.responded_at && <form onSubmit={respond} className="mt-4"><label htmlFor="peer-review-response" className="block text-sm font-semibold text-ink">Optional response to your partner</label><textarea id="peer-review-response" required maxLength={500} rows={3} value={responseText} onChange={(event) => setResponseText(event.target.value)} className="mt-2 w-full rounded-lg border border-line bg-white p-3 text-base leading-6 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" /><span className="mt-1 block text-xs text-muted">{responseText.length}/500</span><button type="submit" disabled={actionBusy || !responseText.trim()} className="mt-3 rounded-full border border-line px-4 py-2.5 text-sm font-semibold text-navy focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50">{actionBusy ? "Sending…" : "Send response"}</button></form>}
      </div>}
      {status.eligible && !status.reviewable_revision && !status.submitted_by_you && !status.review_given && <p className="mt-5 rounded-xl bg-paper p-4 text-sm leading-6 text-muted" role="status">There is no new review round. Your partner’s contribution has already been reviewed or has not changed since round one.</p>}
    </>}
  </section>;
}
