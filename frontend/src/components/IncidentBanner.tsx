import { CHANNEL_LABELS, Incident } from "@/lib/types";

export function IncidentBanner({ incidents }: { incidents: Incident[] }) {
  const active = incidents.filter((i) => i.active);

  if (active.length === 0) {
    return (
      <div className="card px-4 py-3 flex items-center gap-2 text-sm">
        <span
          className="inline-block w-2 h-2 rounded-full shrink-0"
          style={{ background: "var(--status-good)" }}
          aria-hidden
        />
        <span className="text-secondary">All channels operating within normal parameters.</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {active.map((incident) => (
        <div
          key={incident.id}
          className="card px-4 py-3 flex items-center gap-3 text-sm"
          style={{ borderColor: "color-mix(in srgb, var(--status-serious) 40%, var(--border))" }}
        >
          <span
            className="inline-block w-2 h-2 rounded-full shrink-0"
            style={{ background: "var(--status-serious)" }}
            aria-hidden
          />
          <span className="font-medium">{CHANNEL_LABELS[incident.channel]}</span>
          <span className="text-secondary">{incident.description}</span>
          <span className="text-muted text-xs ml-auto">
            since {new Date(incident.started_at).toLocaleTimeString()}
          </span>
        </div>
      ))}
    </div>
  );
}
