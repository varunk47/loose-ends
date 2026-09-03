import { useState } from "react";
import type { Account } from "@/lib/api";

const LABEL: Record<string, string> = {
  discovered: "found",
  planned: "planned",
  awaiting_decision: "needs you",
  in_progress: "in progress",
  sent: "notice sent",
  awaiting_reply: "waiting on reply",
  follow_up: "chasing",
  done: "done",
  failed: "failed",
  parked: "parked",
  watching: "watching",
};
const PILL: Record<string, string> = { awaiting_decision: "needs", awaiting_reply: "waiting", follow_up: "waiting", done: "done", parked: "parked", failed: "parked" };

export function Ledger({ accounts, busy, onReply }: {
  accounts: Account[];
  busy: boolean;
  onReply: (id: string, body: string) => void;
}) {
  const [replying, setReplying] = useState<string | null>(null);
  const [body, setBody] = useState("We have closed the account and issued a refund.");
  const money = accounts.filter((a) => a.monthly_amount && a.status !== "done").reduce((s, a) => s + (a.monthly_amount ?? 0), 0);

  return (
    <section>
      <header>
        <h2>Every account, and where it stands</h2>
        <p>{money > 0 ? `$${money.toFixed(2)} a month still being billed` : ""}</p>
      </header>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>Organization</th><th>Kind</th><th>Status</th><th className="num">Evidence</th><th className="num">Monthly</th><th></th></tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className={a.status === "awaiting_decision" ? "row-needs" : ""}>
                <td>{a.vendor}<div className="domain">{a.domain}</div></td>
                <td>{a.category.replace("_", " ")}</td>
                <td><span className={`pill ${PILL[a.status] ?? ""}`}>{LABEL[a.status] ?? a.status}</span></td>
                <td className="num">{a.evidence.length}</td>
                <td className="num">{a.monthly_amount ? `$${a.monthly_amount.toFixed(2)}` : ""}</td>
                <td>
                  {a.status === "awaiting_reply" && replying !== a.id && (
                    <button className="btn quiet" disabled={busy} onClick={() => setReplying(a.id)}>Simulate reply</button>
                  )}
                  {replying === a.id && (
                    <span className="controls">
                      <input value={body} onChange={(e) => setBody(e.target.value)} aria-label="Reply text" style={{ width: "18rem" }} />
                      <button className="btn" disabled={busy} onClick={() => { onReply(a.id, body); setReplying(null); }}>Send reply</button>
                      <button className="btn ghost" onClick={() => setReplying(null)}>Cancel</button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
