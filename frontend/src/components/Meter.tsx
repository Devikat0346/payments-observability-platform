interface MeterProps {
  label: string;
  pct: number; // error-budget burn, 0-100 nominal, can exceed 100
}

function severityColor(pct: number): string {
  if (pct >= 100) return "var(--status-critical)";
  if (pct >= 70) return "var(--status-warning)";
  return "var(--seq-blue-450)";
}

export function Meter({ label, pct }: MeterProps) {
  const display = Math.min(pct, 100);
  const color = severityColor(pct);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-secondary">{label}</span>
        <span className="text-secondary font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
          {pct.toFixed(0)}%
        </span>
      </div>
      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ background: "var(--seq-blue-300)", opacity: 0.25 }}
      >
      </div>
      <div
        className="h-2 rounded-full -mt-2 transition-all duration-500"
        style={{ width: `${display}%`, background: color }}
      />
    </div>
  );
}
