"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Play,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Cpu,
  Coins,
  ChevronRight,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { api, type Run } from "@/lib/api";

export default function DashboardPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [stats, setStats] = useState({
    total: 0,
    running: 0,
    completed: 0,
    failed: 0,
    totalTokens: 0,
    estimatedCost: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>("/runs", { params: { page_size: 15 } })
      .then((data) => {
        setRuns(data.items);
        const list: Run[] = data.items;
        const running = list.filter((r) => ["running", "pending", "paused_hitl"].includes(r.status)).length;
        const completed = list.filter((r) => r.status === "completed").length;
        const failed = list.filter((r) => r.status === "failed").length;
        const totalTokens = list.reduce((acc, r) => acc + r.total_tokens_in + r.total_tokens_out, 0);
        const estimatedCost = list.reduce((acc, r) => acc + parseFloat(r.total_cost_usd || "0"), 0);
        setStats({ total: data.total || list.length, running, completed, failed, totalTokens, estimatedCost });
      })
      .catch((err) => console.error("Error loading dashboard metrics:", err))
      .finally(() => setLoading(false));
  }, []);

  const chartData = [
    { name: "Mon", tokens: 12000, runs: 3 },
    { name: "Tue", tokens: 19000, runs: 5 },
    { name: "Wed", tokens: 32000, runs: 8 },
    { name: "Thu", tokens: 28000, runs: 6 },
    { name: "Fri", tokens: 45000, runs: 12 },
    { name: "Sat", tokens: 15000, runs: 4 },
    { name: "Sun", tokens: 22000, runs: 7 },
  ];

  const pieData = [
    { name: "Completed", value: stats.completed || 1, color: "#42be65" },
    { name: "Failed", value: stats.failed, color: "#ff8389" },
    { name: "Running", value: stats.running, color: "#4589ff" },
  ].filter((item) => item.value > 0);

  if (loading) {
    return (
      <div style={{ padding: "var(--spacing-07)", display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ height: 28, width: 200 }} className="skeleton" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}>
          {[1, 2, 3, 4].map((i) => <div key={i} style={{ height: 112 }} className="skeleton" />)}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
          <div style={{ height: 300 }} className="skeleton" />
          <div style={{ height: 300 }} className="skeleton" />
        </div>
      </div>
    );
  }

  return (
    <div
      className="animate-fade-in"
      style={{ padding: "var(--spacing-07)", display: "flex", flexDirection: "column", gap: 32 }}
    >
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Workspace Overview</h1>
          <p className="page-subtitle">Real-time analytics for your self-hosted agent workflows.</p>
        </div>
      </div>

      {/* ── Metric Cards ─────────────────────────────────────────────── */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 1,
          background: "var(--cds-border-subtle-00)",
          border: "1px solid var(--cds-border-subtle-00)",
        }}
      >
        {[
          {
            icon: <Play className="w-5 h-5" style={{ color: "var(--cds-interactive)" }} />,
            value: stats.total,
            label: "Total Executions",
            badge: <span className="status-badge status-running" style={{ fontSize: "0.6875rem" }}>Active</span>,
          },
          {
            icon: <CheckCircle2 className="w-5 h-5" style={{ color: "var(--cds-support-success)" }} />,
            value: `${stats.total > 0 ? Math.round((stats.completed / (stats.total || 1)) * 100) : 0}%`,
            label: "Completion Rate",
            valueColor: "var(--cds-support-success)",
          },
          {
            icon: <Cpu className="w-5 h-5" style={{ color: "#a56eff" }} />,
            value: `${(stats.totalTokens / 1000).toFixed(1)}k`,
            label: "Tokens Consumed",
          },
          {
            icon: <Coins className="w-5 h-5" style={{ color: "var(--cds-support-warning)" }} />,
            value: `$${stats.estimatedCost.toFixed(4)}`,
            label: "Estimated Cost",
            valueColor: "var(--cds-support-warning)",
          },
        ].map((card, i) => (
          <div
            key={i}
            className="metric-card"
            style={{ borderRadius: 0, border: "none", background: "var(--cds-layer-01)" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
              {card.icon}
              {card.badge}
            </div>
            <p className="metric-value" style={{ color: card.valueColor || "var(--cds-text-primary)" }}>
              {card.value}
            </p>
            <p className="metric-label">{card.label}</p>
          </div>
        ))}
      </section>

      {/* ── Charts ───────────────────────────────────────────────────── */}
      <section style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 1, background: "var(--cds-border-subtle-00)" }}>
        {/* Area chart */}
        <div
          className="glass-card"
          style={{ padding: "var(--spacing-06)", borderRadius: 0, border: "none" }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
              Token Workload — 7 days
            </h2>
            <TrendingUp className="w-4 h-4" style={{ color: "var(--cds-text-helper)" }} />
          </div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 0, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4589ff" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#4589ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" stroke="#6f6f6f" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#6f6f6f" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: "#262626", borderColor: "#525252", borderRadius: 2, fontSize: 12 }}
                  labelStyle={{ color: "#f4f4f4", fontWeight: 600 }}
                />
                <Area type="monotone" dataKey="tokens" stroke="#4589ff" strokeWidth={2} fillOpacity={1} fill="url(#colorTokens)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pie chart */}
        <div
          className="glass-card"
          style={{ padding: "var(--spacing-06)", borderRadius: 0, border: "none" }}
        >
          <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)", marginBottom: 20 }}>
            Execution Results
          </h2>
          <div style={{ height: 160, position: "relative" }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={68} paddingAngle={4} dataKey="value">
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: "1.5rem", fontWeight: 300, color: "var(--cds-text-primary)" }}>{stats.total}</span>
              <span style={{ fontSize: "0.625rem", color: "var(--cds-text-helper)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Runs</span>
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 16, flexWrap: "wrap" }}>
            {pieData.map((item) => (
              <div key={item.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: item.color, flexShrink: 0 }} />
                <span style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>{item.name} ({item.value})</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Recent Runs Table ──────────────────────────────────────────── */}
      <section className="glass-card" style={{ overflow: "hidden" }}>
        <div
          style={{
            padding: "var(--spacing-05) var(--spacing-06)",
            borderBottom: "1px solid var(--cds-border-subtle-00)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
            Recent Execution Traces
          </h2>
          <Link
            href="/dashboard/runs"
            style={{ fontSize: "0.75rem", color: "var(--cds-link-primary)", display: "flex", alignItems: "center", gap: 4, textDecoration: "none" }}
          >
            View all <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="cds-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Status</th>
                <th>Steps</th>
                <th>Tokens</th>
                <th>Duration</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 5).map((run) => (
                <tr key={run.id}>
                  <td>
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", color: "var(--cds-text-primary)" }}>
                      {run.id.slice(0, 16)}…
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge status-${run.status === "paused_hitl" ? "paused" : run.status}`}>
                      {run.status === "paused_hitl" ? "paused (hitl)" : run.status}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{run.total_steps || 0}</td>
                  <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
                    {run.total_tokens_in + run.total_tokens_out}
                  </td>
                  <td style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", fontFamily: "'IBM Plex Mono', monospace" }}>
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <Link href={`/dashboard/workflows/${run.workflow_id}/runs/${run.id}`} className="btn btn-ghost btn-sm">
                      Trace
                    </Link>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: "var(--spacing-08)", textAlign: "center", color: "var(--cds-text-helper)" }}>
                    No executions yet. Create a workflow and run it to begin.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
