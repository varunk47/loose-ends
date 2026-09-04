import type { Money } from "@/lib/api";

export function Thread({ counts, money }: { counts: Record<string, number>; money?: Money }) {
  const n = (k: string) => counts[k] ?? 0;
  const done = n("done");
  const working = n("discovered") + n("planned") + n("in_progress") + n("sent");
  const waiting = n("awaiting_reply") + n("follow_up") + n("watching");
  const needs = n("awaiting_decision");
  const parked = n("parked") + n("failed");
  const total = done + working + waiting + needs + parked || 1;
  const pct = (x: number) => `${(x / total) * 100}%`;

  return (
    <div className="thread" aria-label="Progress">
      <div className="thread-bar">
        <span className="done" style={{ width: pct(done) }} />
        <span className="working" style={{ width: pct(working) }} />
        <span className="waiting" style={{ width: pct(waiting) }} />
        <span className="needs" style={{ width: pct(needs) }} />
      </div>
      <div className="thread-legend">
        <span><i style={{ background: "var(--pine)" }} /><b>{done}</b>done</span>
        <span><i style={{ background: "#7fa89b" }} /><b>{working}</b>being handled</span>
        <span><i style={{ background: "var(--slate)" }} /><b>{waiting}</b>waiting on a reply</span>
        <span><i style={{ background: "var(--amber)" }} /><b>{needs}</b>need you</span>
        {parked > 0 && <span><i style={{ background: "var(--rule)" }} /><b>{parked}</b>parked</span>}
      </div>
      {money && (money.monthly_stopped > 0 || money.refunds_requested > 0) && (
        <p className="money">
          ${money.monthly_stopped.toFixed(2)} a month stopped, {money.refunds_requested} refunds asked for,
          about {Math.round(money.hours_saved)} hours you did not have to spend.
          {money.monthly_pending > 0 ? ` $${money.monthly_pending.toFixed(2)} a month still being billed while replies come in.` : ""}
        </p>
      )}
    </div>
  );
}
