"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Mail, type Status } from "@/lib/api";
import { Thread } from "./thread";
import { Decisions } from "./decisions";
import { Ledger } from "./ledger";
import { Activity } from "./activity";
import { GhostWatch } from "./ghostwatch";
import { SentMail } from "./mail";

export default function Page() {
  const [status, setStatus] = useState<Status | null>(null);
  const [mail, setMail] = useState<Mail[]>([]);
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [today, setToday] = useState("2026-08-10");
  const [brain, setBrain] = useState("offline");

  const refresh = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([api.status(), api.mail()]);
      setStatus(s);
      setMail(m.sent);
      setMissing(false);
    } catch (err) {
      setStatus(null);
      setMissing(true);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const notify = (text: string) => { setToast(text); setTimeout(() => setToast(null), 2500); };

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try { await fn(); await refresh(); notify(done); }
    catch (err) { notify(err instanceof Error ? err.message : "Something went wrong"); }
    finally { setBusy(false); }
  };

  if (missing) {
    return (
      <main className="page">
        <header className="masthead">
          <div>
            <h1>Loose Ends</h1>
            <p>An agent that handles the admin after someone dies.</p>
          </div>
        </header>
        <p className="empty">No estate yet. Start the demo to load Raymond Okafor&apos;s inbox.</p>
        <div className="controls">
          <button className="btn" disabled={busy} onClick={() => run(api.initDemo, "Demo estate created")}>Start the demo</button>
        </div>
      </main>
    );
  }

  if (!status) return <main className="page"><p className="empty">Loading.</p></main>;

  const { estate, counts, open_decisions, accounts, cycles } = status;
  const nextDay = () => {
    const d = new Date(today + "T00:00:00");
    d.setDate(d.getDate() + 1);
    setToday(d.toISOString().slice(0, 10));
  };

  return (
    <main className="page">
      <header className="masthead">
        <div>
          <h1>{estate.deceased}&apos;s affairs</h1>
          <p>{estate.executor_name}, executor. Died {formatDate(estate.date_of_death)}. {accounts.length} accounts found.</p>
        </div>
        <div className="controls">
          <select value={brain} onChange={(e) => setBrain(e.target.value)} aria-label="Model">
            <option value="offline">Offline rules</option>
            <option value="bedrock">Bedrock</option>
          </select>
          <input type="date" value={today} onChange={(e) => setToday(e.target.value)} aria-label="Cycle date" />
          <button className="btn" disabled={busy} onClick={() => run(() => api.cycle(brain, today).then(nextDay), "Cycle finished")}>
            Run a cycle
          </button>
          {estate.paused_until
            ? <button className="btn ghost" disabled={busy} onClick={() => run(() => api.pause(null), "Resumed")}>Resume</button>
            : <button className="btn ghost" disabled={busy} onClick={() => run(() => api.pause(plusDays(today, 7)), "Paused for a week")}>Pause a week</button>}
          <button className="btn ghost" disabled={busy} onClick={() => run(api.reset, "Demo reset")}>Reset demo</button>
        </div>
      </header>

      <Thread counts={counts} money={status.money} />

      {estate.paused_until && (
        <p className="empty">Paused until {formatDate(estate.paused_until)}. Nothing goes out, but Ghost Watch keeps watching.</p>
      )}

      <Decisions
        decisions={open_decisions}
        accounts={accounts}
        busy={busy}
        onAnswer={(id, choice) => run(() => api.answer(id, choice), `Answered: ${choice}`)}
      />

      <Ledger accounts={accounts} busy={busy} onReply={(id, body) => run(() => api.reply(id, body), "Reply queued for the next cycle")} />

      <GhostWatch watches={status.watches} accounts={accounts} />

      <Activity cycles={cycles} />

      <SentMail mail={mail} />

      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  );
}

function plusDays(iso: string, days: number) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatDate(iso: string) {
  return new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}
