export type Rail = "CARD" | "WIRE" | "ACH_BATCH";
export type Channel =
  | "pos"
  | "ecommerce"
  | "mobile_wallet"
  | "wire_online"
  | "wire_branch"
  | "ach_batch_file";
export type Health = "healthy" | "degraded" | "breached";

export interface Incident {
  id: string;
  rail: Rail;
  channel: Channel;
  kind: "latency_spike" | "failure_spike";
  magnitude: number;
  started_at: string;
  ended_at: string | null;
  description: string;
  active: boolean;
}

export interface ChannelMetric {
  channel: Channel;
  rail: Rail;
  health: Health;
  window_seconds: number;
  total: number;
  success: number;
  failure: number;
  success_rate: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  slo_success_rate: number;
  slo_latency_p99_ms: number | null;
  error_budget_burn_pct: number;
  active_incident: Incident | null;
}

export interface RailMetric {
  rail: Rail;
  total: number;
  success: number;
  failure: number;
  success_rate: number | null;
  slo_success_rate: number;
}

export interface MetricsSummary {
  generated_at: string;
  channels: Record<Channel, ChannelMetric>;
  rails: Record<Rail, RailMetric>;
}

export interface Transaction {
  id: string;
  rail: Rail;
  channel: Channel;
  txn_type: "credit" | "debit" | "wire";
  amount: number;
  status:
    | "initiated"
    | "authorized"
    | "declined"
    | "settled"
    | "posted"
    | "failed"
    | "returned";
  created_at: string;
  updated_at: string;
  auth_latency_ms: number | null;
  settle_latency_ms: number | null;
  batch_id: string | null;
  decline_reason: string | null;
  return_code: string | null;
}

export const CHANNEL_LABELS: Record<Channel, string> = {
  pos: "POS / Card-Present",
  ecommerce: "E-Commerce",
  mobile_wallet: "Mobile Wallet",
  wire_online: "Wire — Online",
  wire_branch: "Wire — Branch",
  ach_batch_file: "ACH Batch File",
};

export const RAIL_LABELS: Record<Rail, string> = {
  CARD: "Card (Credit/Debit)",
  WIRE: "Wire Transfer",
  ACH_BATCH: "ACH Batch",
};
