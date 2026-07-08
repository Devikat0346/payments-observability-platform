import { Health } from "@/lib/types";

const HEALTH_CONFIG: Record<Health, { color: string; label: string }> = {
  healthy: { color: "var(--status-good)", label: "Healthy" },
  degraded: { color: "var(--status-warning)", label: "Degraded" },
  breached: { color: "var(--status-critical)", label: "Breached" },
};

export function HealthBadge({ health }: { health: Health }) {
  const cfg = HEALTH_CONFIG[health];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-secondary">
      <span
        className="inline-block w-2 h-2 rounded-full shrink-0"
        style={{ background: cfg.color }}
        aria-hidden
      />
      {cfg.label}
    </span>
  );
}
