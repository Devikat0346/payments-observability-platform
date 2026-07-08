"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL, fetchIncidents, fetchMetricsSummary, fetchRecentTransactions } from "./api";
import { Channel, Incident, MetricsSummary, Transaction } from "./types";

const HISTORY_POINTS = 30;
const FEED_MAX = 60;
const RECONNECT_DELAY_MS = 2000;

export interface HistoryPoint {
  t: number;
  p50: number | null;
  successRate: number | null;
}

type History = Partial<Record<Channel, HistoryPoint[]>>;

export function useLiveData() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [feed, setFeed] = useState<Transaction[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [history, setHistory] = useState<History>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [initialFeed, initialIncidents, initialMetrics] = await Promise.all([
          fetchRecentTransactions(FEED_MAX),
          fetchIncidents(),
          fetchMetricsSummary(),
        ]);
        if (cancelled) return;
        setFeed(initialFeed);
        setIncidents(initialIncidents);
        setMetrics(initialMetrics);
      } catch {
        // backend may not be up yet; the socket loop below will keep retrying
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (cancelled) return;
      socket = new WebSocket(WS_URL);
      wsRef.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };
      socket.onerror = () => socket?.close();

      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "metrics_tick") {
          const summary: MetricsSummary = msg.data;
          setMetrics(summary);
          const t = Date.now();
          setHistory((prev) => {
            const next: History = { ...prev };
            for (const [channel, cm] of Object.entries(summary.channels)) {
              const key = channel as Channel;
              const points = [...(next[key] ?? [])];
              points.push({ t, p50: cm.p50_latency_ms, successRate: cm.success_rate });
              next[key] = points.slice(-HISTORY_POINTS);
            }
            return next;
          });
        } else if (msg.type === "transaction") {
          setFeed((prev) => [msg.data as Transaction, ...prev].slice(0, FEED_MAX));
        } else if (msg.type === "incident_start" || msg.type === "incident_end") {
          const incident: Incident = msg.data;
          setIncidents((prev) => {
            const withoutDup = prev.filter((i) => i.id !== incident.id);
            return [incident, ...withoutDup].slice(0, 50);
          });
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return { metrics, feed, incidents, history, connected };
}
