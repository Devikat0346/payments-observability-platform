"use client";

import { ChannelCard } from "@/components/ChannelCard";
import { IncidentBanner } from "@/components/IncidentBanner";
import { LiveFeed } from "@/components/LiveFeed";
import { StatTile } from "@/components/StatTile";
import { useLiveData } from "@/lib/useLiveData";
import { CHANNEL_LABELS, Channel } from "@/lib/types";

const CHANNEL_ORDER: Channel[] = [
  "pos",
  "ecommerce",
  "mobile_wallet",
  "wire_online",
  "wire_branch",
  "ach_batch_file",
];

export default function Home() {
  const { metrics, feed, incidents, history, connected } = useLiveData();

  const channels = metrics ? Object.values(metrics.channels) : [];
  const totalTxns = channels.reduce((sum, c) => sum + c.total, 0);
  const totalSuccess = channels.reduce((sum, c) => sum + c.success, 0);
  const overallSuccessRate = totalTxns > 0 ? totalSuccess / totalTxns : null;
  const activeIncidentCount = incidents.filter((i) => i.active).length;
  const worstBurn = channels.length
    ? Math.max(...channels.map((c) => c.error_budget_burn_pct))
    : 0;

  return (
    <div className="min-h-screen px-6 py-10 md:px-12 lg:px-20 max-w-[1400px] mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Multi-Rail Payments Observability Platform
          </h1>
          <p className="text-secondary text-sm mt-1">
            Simulated credit, debit &amp; wire transactions across real-time and batch origination
            channels — with live SLIs, SLOs, and error-budget tracking.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm shrink-0">
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ background: connected ? "var(--status-good)" : "var(--status-critical)" }}
            aria-hidden
          />
          <span className="text-secondary">{connected ? "Live" : "Reconnecting…"}</span>
        </div>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatTile
          label="Transactions (5m window)"
          value={totalTxns.toLocaleString()}
          sublabel="across all channels"
        />
        <StatTile
          label="Overall success rate"
          value={overallSuccessRate !== null ? `${(overallSuccessRate * 100).toFixed(2)}%` : "—"}
        />
        <StatTile
          label="Active incidents"
          value={String(activeIncidentCount)}
          sublabel={activeIncidentCount ? "channels degraded" : "all clear"}
        />
        <StatTile
          label="Worst error-budget burn"
          value={`${worstBurn.toFixed(0)}%`}
          sublabel="30m rolling window"
        />
      </section>

      <section className="mb-8">
        <IncidentBanner incidents={incidents} />
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-secondary uppercase tracking-wide mb-3">
          Channels &amp; rails
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {CHANNEL_ORDER.map((channel) => {
            const metric = metrics?.channels[channel];
            if (!metric) {
              return (
                <div key={channel} className="card p-5 text-muted text-sm">
                  {CHANNEL_LABELS[channel]} — collecting data…
                </div>
              );
            }
            return (
              <ChannelCard key={channel} metric={metric} history={history[channel] ?? []} />
            );
          })}
        </div>
      </section>

      <section>
        <LiveFeed transactions={feed} />
      </section>

      <footer className="mt-12 text-muted text-xs">
        Synthetic data, generated in-process for demonstration purposes. No real payment data is
        used or stored.
      </footer>
    </div>
  );
}
