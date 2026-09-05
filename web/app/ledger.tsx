import { Fragment, useState } from "react";
import type { Account, Action } from "@/lib/api";

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

const ACTION_WORDS: Record<string, string> = {
  "email:sent": "Notice sent",
  "form:submitted": "Form submitted",
  "form:queued": "Form queued for the browser agent",
  "call:scheduled": "Call scheduled",
  "dispute:sent": "Dispute sent",
  "reply:closed": "They confirmed it is closed",
  "reply:needs_documents": "They asked for documents",
  "reply:wrong_channel": "They asked for a different channel",
  "reply:denied": "They declined",
  "reply:other": "They replied",
};

export function Ledger({ accounts, actions, busy, onReply }: {
  accounts: Account[];
  actions: Action[];
  busy: boolean;
  onReply: (id: string, body: string) => void;
}) {
  const [replying, setReplying] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [body, setBody] = useState("We have closed the account and issued a refund.");
  const money = accounts.filter((a) => a.monthly_amount && a.status !== "done").reduce((s, a) => s + (a.monthly_amount ?? 0), 0);
  const byAccount = (id: string) => actions.filter((a) => a.account_id === id);

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
              <Fragment key={a.id}>
                <tr className={a.status === "awaiting_decision" ? "row-needs" : ""}>
                  <td>
                    <button className="linklike" onClick={() => setOpen(open === a.id ? null : a.id)} aria-expanded={open === a.id}>{a.vendor}</button>
                    <div className="domain">{a.domain}</div>
                  </td>
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
                {open === a.id && (
                  <tr className="detail">
                    <td colSpan={6}>
                      <div className="detail-grid">
                        <div>
                          <strong>What happened</strong>
                          {byAccount(a.id).length === 0 && <p>Nothing yet.</p>}
                          <ol className="timeline compact">
                            {byAccount(a.id).map((act) => (
                              <li key={act.id}>
                                <time dateTime={act.at}>{new Date(act.at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</time>
                                <span>{ACTION_WORDS[`${act.type}:${act.result}`] ?? `${act.type} ${act.result}`}{typeof act.payload.to === "string" ? ` to ${act.payload.to}` : ""}{typeof act.payload.summary === "string" ? `: ${act.payload.summary}` : ""}</span>
                              </li>
                            ))}
                          </ol>
                        </div>
                        <div>
                          <strong>Why it is here</strong>
                          <p>Found in {a.evidence.length} message{a.evidence.length === 1 ? "" : "s"}{a.playbook ? `, handled with the ${a.playbook.replace("_", " ")} playbook` : ""}. Confidence {Math.round(a.confidence * 100)}%.</p>
                          {a.notes && <p>Notes: {a.notes}</p>}
                          {a.next_action_at && <p>Next check: {new Date(a.next_action_at).toLocaleDateString("en-US", { month: "long", day: "numeric" })}</p>}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
