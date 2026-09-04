import type { Account, Watch } from "@/lib/api";

const LABEL: Record<string, string> = {
  zombie_charge: "charged after closing",
  new_account: "new account opened",
  credit_inquiry: "credit inquiry",
};
const STATE: Record<string, string> = { open: "waiting for you", sent: "dispute sent", ignored: "ignored" };

export function GhostWatch({ watches, accounts }: { watches: Watch[]; accounts: Account[] }) {
  const vendor = (id: string) => accounts.find((a) => a.id === id)?.vendor ?? "";
  return (
    <section>
      <header>
        <h2>Ghost Watch</h2>
        <p>{watches.length === 0 ? "" : `${watches.length} caught`}</p>
      </header>
      {watches.length === 0 && (
        <p className="empty">Watching new mail for charges after closure, accounts opened in {""}
          the deceased&apos;s name, and credit inquiries. Nothing caught so far.</p>
      )}
      {watches.length > 0 && (
        <ol className="timeline">
          {[...watches].reverse().map((w) => (
            <li key={w.id}>
              <time dateTime={w.at}>{new Date(w.at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</time>
              <span>
                <strong>{vendor(w.account_id)}</strong>, {LABEL[w.signal] ?? w.signal}. {w.summary}
                <span className={`pill ${w.status === "open" ? "needs" : w.status === "sent" ? "done" : "parked"}`} style={{ marginLeft: "0.6rem" }}>
                  {STATE[w.status] ?? w.status}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
