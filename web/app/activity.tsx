import type { Cycle } from "@/lib/api";

const WORDS: Array<[string, string]> = [
  ["discovered", "accounts found"],
  ["sent", "notices sent"],
  ["decisions", "questions for you"],
  ["queued", "forms queued"],
  ["resumed", "resumed after your answer"],
  ["replies", "replies read"],
  ["closed", "closed"],
  ["chased", "second notices"],
  ["escalated", "escalated"],
  ["answers", "answered by email"],
  ["parked", "parked"],
  ["ghost_hits", "caught by Ghost Watch"],
];

export function Activity({ cycles }: { cycles: Cycle[] }) {
  return (
    <section>
      <header>
        <h2>What happened while you were away</h2>
        <p>{cycles.length === 0 ? "" : `${cycles.length} cycle${cycles.length > 1 ? "s" : ""}`}</p>
      </header>
      {cycles.length === 0 && <p className="empty">No cycles yet. Run one to see the agent work.</p>}
      {cycles.length > 0 && (
        <ol className="timeline">
          {[...cycles].reverse().map((c) => {
            const parts = WORDS.filter(([k]) => Number(c.summary[k]) > 0).map(([k, w]) => `${c.summary[k]} ${w}`);
            return (
              <li key={c.id}>
                <time dateTime={c.at}>{new Date(c.at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time>
                <span>{parts.length ? parts.join(", ") : "Checked in, nothing new"}{c.summary.digest_sent ? ". Digest sent." : ""}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
