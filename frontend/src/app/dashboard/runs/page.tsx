"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PlaySquare, RefreshCw, ChevronRight } from "lucide-react";
import { api, type Run } from "@/lib/api";

export default function RunsHistoryPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const loadRuns = () => {
    setLoading(true);
    api.get<any>("/runs", { params: { page, page_size: pageSize } })
      .then((data) => { setRuns(data.items); setTotal(data.total); })
      .catch((err) => console.error("Error loading run logs:", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadRuns(); }, [page]);

  const totalPages = Math.ceil(total / pageSize);

  if (loading && runs.length === 0) {
    return (
      <div style={{ padding: "var(--spacing-07)", display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ height: 28, width: 200 }} className="skeleton" />
        <div style={{ height: 400 }} className="skeleton" />
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
          <h1 className="page-title">Execution Logs</h1>
          <p className="page-subtitle">Audit history of all workflow state machine runs.</p>
        </div>
        <button onClick={loadRuns} className="btn btn-ghost">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* DataTable */}
      <section className="glass-card" style={{ overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table className="cds-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Status</th>
                <th>Steps</th>
                <th>Token Workload</th>
                <th>Duration</th>
                <th>Triggered</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}>
                      {run.id}
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
                  <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : "—"}
                  </td>
                  <td style={{ fontSize: "0.75rem", color: "var(--cds-text-helper)" }}>
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <Link
                      href={`/dashboard/workflows/${run.workflow_id}/runs/${run.id}`}
                      className="btn btn-ghost btn-sm"
                    >
                      Trace <ChevronRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    style={{ padding: "var(--spacing-08)", textAlign: "center", color: "var(--cds-text-helper)" }}
                  >
                    No executions in this workspace yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "var(--spacing-04) var(--spacing-05)",
              borderTop: "1px solid var(--cds-border-subtle-00)",
              background: "var(--cds-layer-02)",
            }}
          >
            <span style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
              Page {page} of {totalPages} — {total} total runs
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button disabled={page === 1} onClick={() => setPage(page - 1)} className="btn btn-ghost btn-sm">
                Previous
              </button>
              <button disabled={page === totalPages} onClick={() => setPage(page + 1)} className="btn btn-ghost btn-sm">
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
