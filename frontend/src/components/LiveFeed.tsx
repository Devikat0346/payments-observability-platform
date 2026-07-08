import { CHANNEL_LABELS, Transaction } from "@/lib/types";

const STATUS_COLOR: Record<Transaction["status"], string> = {
  initiated: "var(--text-muted)",
  authorized: "var(--seq-blue-450)",
  settled: "var(--status-good)",
  posted: "var(--status-good)",
  declined: "var(--status-critical)",
  failed: "var(--status-critical)",
  returned: "var(--status-serious)",
};

function fmtMoney(v: number): string {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function LiveFeed({ transactions }: { transactions: Transaction[] }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
        <h3 className="font-semibold">Live transaction feed</h3>
      </div>
      <div className="max-h-96 overflow-y-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted text-xs sticky top-0" style={{ background: "var(--surface-card)" }}>
              <th className="px-5 py-2 font-medium">Time</th>
              <th className="px-5 py-2 font-medium">Channel</th>
              <th className="px-5 py-2 font-medium">Amount</th>
              <th className="px-5 py-2 font-medium">Status</th>
              <th className="px-5 py-2 font-medium">Latency</th>
            </tr>
          </thead>
          <tbody>
            {transactions.slice(0, 30).map((txn) => (
              <tr key={`${txn.id}-${txn.status}`} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                <td className="px-5 py-2 text-muted" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {new Date(txn.updated_at).toLocaleTimeString()}
                </td>
                <td className="px-5 py-2">{CHANNEL_LABELS[txn.channel]}</td>
                <td className="px-5 py-2" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {fmtMoney(txn.amount)}
                </td>
                <td className="px-5 py-2">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: STATUS_COLOR[txn.status] }}
                      aria-hidden
                    />
                    {txn.status}
                  </span>
                </td>
                <td className="px-5 py-2 text-secondary" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {txn.auth_latency_ms ? `${txn.auth_latency_ms.toFixed(0)}ms` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {transactions.length === 0 && (
          <div className="px-5 py-8 text-center text-muted text-sm">Waiting for transactions…</div>
        )}
      </div>
    </div>
  );
}
