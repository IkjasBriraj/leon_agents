"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { GitBranch, Plus, Trash2, Calendar, ArrowRight, X } from "lucide-react";
import { api, type Workflow } from "@/lib/api";

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [modalError, setModalError] = useState<string | null>(null);

  const loadWorkflows = () => {
    setLoading(true);
    api.get<any>("/workflows")
      .then((data) => setWorkflows(data.items))
      .catch((err) => setError(err.message || "Failed to load workflows"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadWorkflows(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);
    try {
      const data = await api.post<{ id: string }>("/workflows", {
        name,
        description: description || null,
        nodes: [
          { node_key: "start", node_type: "start", label: "Start", position_x: 100, position_y: 200 },
          { node_key: "end", node_type: "end", label: "End", position_x: 600, position_y: 200 },
        ],
        edges: [],
      });
      setIsOpen(false); setName(""); setDescription("");
      router.push(`/dashboard/workflows/${data.id}/builder`);
    } catch (err: any) {
      setModalError(err.message || "Failed to create workflow");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this workflow? All associated runs will also be removed.")) return;
    try {
      await api.delete(`/workflows/${id}`);
      loadWorkflows();
    } catch (err: any) {
      alert(err.message || "Failed to delete workflow");
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "var(--spacing-07)", display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ height: 28, width: 200 }} className="skeleton" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 1, background: "var(--cds-border-subtle-00)" }}>
          {[1, 2, 3].map((i) => <div key={i} style={{ height: 176, background: "var(--cds-layer-01)" }} className="skeleton" />)}
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
          <h1 className="page-title">Workflow Library</h1>
          <p className="page-subtitle">Design state machines, loops, and conditional reasoning graphs.</p>
        </div>
        <button onClick={() => setIsOpen(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> New Workflow
        </button>
      </div>

      {error && <div className="cds-notification error"><span>{error}</span></div>}

      {/* Workflow cards */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 1,
          background: workflows.length > 0 ? "var(--cds-border-subtle-00)" : "transparent",
        }}
      >
        {workflows.map((flow) => (
          <div
            key={flow.id}
            style={{
              background: "var(--cds-layer-01)",
              padding: "var(--spacing-05)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: 176,
              transition: "background var(--transition)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--cds-layer-hover-01)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "var(--cds-layer-01)")}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    className="cds-icon-box"
                    style={{ background: "rgba(69,137,255,0.10)", border: "1px solid rgba(69,137,255,0.20)", color: "var(--cds-link-primary)" }}
                  >
                    <GitBranch className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {flow.name}
                    </h3>
                    <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)" }}>
                      v{flow.version}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {flow.is_cyclic && (
                    <span className="cds-tag yellow">Cyclic</span>
                  )}
                  <span className="status-badge status-complete">{flow.status}</span>
                </div>
              </div>

              <p style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                {flow.description || "No description specified. Open the visual editor to model nodes."}
              </p>
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                paddingTop: 12,
                borderTop: "1px solid var(--cds-border-subtle-00)",
                marginTop: 12,
              }}
            >
              <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", display: "flex", alignItems: "center", gap: 4 }}>
                <Calendar className="w-3.5 h-3.5" />
                {new Date(flow.created_at).toLocaleDateString()}
              </span>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  onClick={() => handleDelete(flow.id)}
                  className="btn btn-ghost btn-icon"
                  title="Delete workflow"
                  style={{ color: "var(--cds-support-error)" }}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <Link href={`/dashboard/workflows/${flow.id}/builder`} className="btn btn-ghost btn-sm">
                  Open <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </div>
        ))}

        {workflows.length === 0 && (
          <div
            style={{
              padding: "var(--spacing-09)",
              textAlign: "center",
              color: "var(--cds-text-helper)",
              fontSize: "0.875rem",
              border: "1px dashed var(--cds-border-subtle-01)",
              width: "100%",
            }}
          >
            No workflows found. Click "New Workflow" to start the visual builder.
          </div>
        )}
      </section>

      {/* ── Create Workflow Modal ────────────────────────────────────── */}
      {isOpen && (
        <div className="cds-modal-overlay animate-fade-in">
          <div className="cds-modal" style={{ maxWidth: 440 }}>
            <div className="cds-modal-header">
              <h2 className="cds-modal-title">New Workflow</h2>
              <button onClick={() => setIsOpen(false)} className="cds-modal-close">
                <X className="w-5 h-5" />
              </button>
            </div>

            {modalError && (
              <div className="cds-notification error" style={{ margin: "var(--spacing-05) var(--spacing-06) 0" }}>
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleCreate}>
              <div className="cds-modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label className="input-label">Workflow Name</label>
                  <input
                    type="text" required className="input"
                    placeholder="e.g. Code QA Pipeline"
                    value={name} onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="input-label">Description</label>
                  <textarea
                    className="input"
                    placeholder="Summarize graph goals (Start → Agent → Tool → End)…"
                    value={description} onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
              </div>
              <div className="cds-modal-footer">
                <button type="button" onClick={() => setIsOpen(false)} className="btn btn-ghost">Cancel</button>
                <button type="submit" className="btn btn-primary">Create &amp; Open Builder</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
