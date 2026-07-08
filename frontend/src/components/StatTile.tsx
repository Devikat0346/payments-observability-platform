interface StatTileProps {
  label: string;
  value: string;
  sublabel?: string;
}

export function StatTile({ label, value, sublabel }: StatTileProps) {
  return (
    <div className="card p-5 flex flex-col gap-1">
      <span className="text-muted text-sm">{label}</span>
      <span className="text-3xl font-semibold tracking-tight">{value}</span>
      {sublabel && <span className="text-secondary text-xs">{sublabel}</span>}
    </div>
  );
}
