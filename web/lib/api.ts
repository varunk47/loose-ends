export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Account = {
  id: string;
  vendor: string;
  domain: string;
  category: string;
  status: string;
  priority: number;
  evidence: string[];
  confidence: number;
  playbook: string | null;
  monthly_amount: number | null;
  next_action_at: string | null;
  notes: string;
};

export type Decision = {
  id: string;
  account_id: string;
  question: string;
  options: string[];
  context: string;
  created_at: string;
};

export type Cycle = { id: string; at: string; summary: Record<string, number | boolean> };

export type Status = {
  estate_id: string;
  estate: { deceased: string; date_of_death: string; executor_name: string; executor_email: string };
  counts: Record<string, number>;
  open_decisions: Decision[];
  accounts: Account[];
  cycles: Cycle[];
};

export type Mail = { id: string; to: string; subject: string; body: string; attachments: string[]; sent_at: string };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export const api = {
  status: () => call<Status>("/api/status"),
  mail: () => call<{ sent: Mail[] }>("/api/mail"),
  initDemo: () => call<{ estate_id: string }>("/api/init-demo", { method: "POST" }),
  cycle: (brain: string, today: string) =>
    call<{ report: Record<string, number | boolean> }>("/api/cycle", { method: "POST", body: JSON.stringify({ brain, today }) }),
  answer: (id: string, choice: string) =>
    call("/api/decisions/" + id + "/answer", { method: "POST", body: JSON.stringify({ choice }) }),
  reply: (account_id: string, body: string) =>
    call("/api/reply", { method: "POST", body: JSON.stringify({ account_id, body }) }),
  reset: () => call("/api/reset", { method: "POST" }),
};
