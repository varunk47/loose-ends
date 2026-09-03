import type { Account, Decision } from "@/lib/api";

export function Decisions({ decisions, accounts, busy, onAnswer }: {
  decisions: Decision[];
  accounts: Account[];
  busy: boolean;
  onAnswer: (id: string, choice: string) => void;
}) {
  const vendorOf = (id: string) => accounts.find((a) => a.id === id);
  return (
    <section>
      <header>
        <h2>Things only you can decide</h2>
        <p>{decisions.length === 0 ? "" : `${decisions.length} waiting`}</p>
      </header>
      {decisions.length === 0 && <p className="empty">Nothing needs you right now. The agent keeps working in the background.</p>}
      {decisions.map((d) => {
        const account = vendorOf(d.account_id);
        return (
          <article className="decision" key={d.id}>
            <div>
              <h3>{d.question}</h3>
              <small>
                {account ? `${account.vendor}, ${account.category.replace("_", " ")}` : ""}
                {account && account.evidence.length > 0 ? `, found in ${account.evidence.length} email${account.evidence.length > 1 ? "s" : ""}` : ""}
              </small>
            </div>
            <div className="options">
              {d.options.map((o) => (
                <button key={o} disabled={busy} onClick={() => onAnswer(d.id, o)}>{capitalize(o)}</button>
              ))}
            </div>
          </article>
        );
      })}
    </section>
  );
}

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
