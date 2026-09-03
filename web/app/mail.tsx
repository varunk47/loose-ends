import type { Mail } from "@/lib/api";

export function SentMail({ mail }: { mail: Mail[] }) {
  return (
    <section>
      <header>
        <h2>Everything the agent sent</h2>
        <p>{mail.length === 0 ? "" : `${mail.length} messages`}</p>
      </header>
      {mail.length === 0 && <p className="empty">Nothing sent yet.</p>}
      {mail.map((m) => (
        <details className="mail" key={m.id}>
          <summary>
            <span>{m.subject}</span>
            <span className="to">to {m.to}{m.attachments.length ? ", certificate attached" : ""}</span>
          </summary>
          <pre>{m.body}</pre>
        </details>
      ))}
    </section>
  );
}
