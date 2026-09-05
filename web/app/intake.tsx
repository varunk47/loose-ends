import { useState } from "react";
import { api } from "@/lib/api";

const PACKET = [
  ["certificate", "Death certificate"],
  ["executor_id", "My photo ID"],
  ["authority_proof", "Letters Testamentary or other proof I am the executor"],
];

export function Intake({ busy, onStarted, onDemo }: { busy: boolean; onStarted: () => void; onDemo: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const packet = PACKET.map(([k]) => k).filter((k) => form.get(`packet_${k}`) === "on");
    form.set("packet", packet.join(","));
    PACKET.forEach(([k]) => form.delete(`packet_${k}`));
    setSaving(true);
    setError(null);
    try { await api.createEstate(form); onStarted(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not create the estate"); }
    finally { setSaving(false); }
  };

  return (
    <section>
      <header>
        <h2>Start with what you have</h2>
        <p>Nothing is sent until you have seen the plan.</p>
      </header>
      <form className="intake" onSubmit={submit}>
        <label>Who died<input name="deceased" required placeholder="Full name" /></label>
        <label>Date of death<input name="date_of_death" type="date" required /></label>
        <label>Your name<input name="executor_name" required /></label>
        <label>Your email<input name="executor_email" type="email" required placeholder="Where the daily digest goes" /></label>
        <label>Your relationship<input name="executor_relationship" defaultValue="executor" placeholder="daughter and executor" /></label>
        <label>State<input name="state" required placeholder="IL" maxLength={2} /></label>
        <label className="wide">Their inbox export<input name="inbox" type="file" accept=".mbox,.json" required />
          <small>Google Takeout gives you a .mbox. Everything stays on this machine.</small></label>
        <fieldset className="wide">
          <legend>Documents you have today</legend>
          {PACKET.map(([k, label]) => (
            <label key={k} className="check"><input type="checkbox" name={`packet_${k}`} defaultChecked={k === "certificate"} />{label}</label>
          ))}
          <small>Organizations that need a document you do not have yet will wait as a question, not a half-sent notice.</small>
        </fieldset>
        {error && <p className="error wide">{error}</p>}
        <div className="wide controls">
          <button className="btn" type="submit" disabled={busy || saving}>Create the estate</button>
          <button className="btn ghost" type="button" disabled={busy || saving} onClick={onDemo}>Or load the demo estate</button>
        </div>
      </form>
    </section>
  );
}
