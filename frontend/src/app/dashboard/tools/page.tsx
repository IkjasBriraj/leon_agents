"use client";

import React, { useEffect, useState } from "react";
import { Wrench, Plus, Terminal, Trash2, Cpu, UserCheck, Check, Code, ShieldAlert, X } from "lucide-react";
import { api, type Tool } from "@/lib/api";

export default function ToolsRegistryPage() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("custom");
  const [functionCode, setFunctionCode] = useState(
    "def custom_tool(query: str) -> str:\n    # Write Python tool logic here\n    return f'Processed query: {query}'"
  );
  const [mcpServerUrl, setMcpServerUrl] = useState("");
  const [parametersSchemaStr, setParametersSchemaStr] = useState(
    '{\n  "type": "object",\n  "properties": {\n    "query": { "type": "string", "description": "The query parameter" }\n  },\n  "required": ["query"]\n}'
  );
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [sandboxRequired, setSandboxRequired] = useState(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState(30);
  const [submitting, setSubmitting] = useState(false);

  const loadTools = () => {
    setLoading(true); setError(null);
    api.get<Tool[]>("/tools")
      .then((data) => setTools(data))
      .catch((err) => setError(err.message || "Failed to load tools"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadTools(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true); setError(null);
    try {
      let parsedSchema = {};
      try { parsedSchema = JSON.parse(parametersSchemaStr); }
      catch { throw new Error("Invalid JSON parameter schema"); }
      await api.post("/tools", {
        name: name.trim().replace(/[^a-zA-Z0-9_]/g, "_"),
        description, category,
        function_code: category === "custom" ? functionCode : null,
        mcp_server_url: category === "mcp" ? mcpServerUrl : null,
        parameters_schema: parsedSchema,
        requires_approval: requiresApproval,
        sandbox_required: sandboxRequired,
        timeout_seconds: timeoutSeconds,
      });
      setIsOpen(false);
      setName(""); setDescription(""); setCategory("custom");
      setFunctionCode("def custom_tool(query: str) -> str:\n    return f'Processed query: {query}'");
      setMcpServerUrl("");
      setParametersSchemaStr('{\n  "type": "object",\n  "properties": {\n    "query": { "type": "string" }\n  },\n  "required": ["query"]\n}');
      setRequiresApproval(false); setSandboxRequired(false); setTimeoutSeconds(30);
      loadTools();
    } catch (err: any) {
      setError(err.message || "Failed to register tool");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this tool?")) return;
    try {
      await api.delete(`/tools/${id}`);
      loadTools();
    } catch (err: any) {
      setError(err.message || "Failed to delete tool");
    }
  };

  const getCategoryTag = (cat: string) => {
    if (cat === "builtin") return <span className="cds-tag blue">builtin</span>;
    if (cat === "mcp") return <span className="cds-tag purple">mcp</span>;
    return <span className="cds-tag green">custom</span>;
  };

  return (
    <div
      className="animate-fade-in"
      style={{ padding: "var(--spacing-07)", maxWidth: 1100, display: "flex", flexDirection: "column", gap: 32 }}
    >
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Tools Registry</h1>
          <p className="page-subtitle">Register Python scripts, webhooks, and MCP server endpoints.</p>
        </div>
        <button onClick={() => setIsOpen(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Register Tool
        </button>
      </div>

      {error && (
        <div className="cds-notification error">
          <ShieldAlert className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tools grid */}
      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--cds-border-subtle-00)" }}>
          {[1, 2, 3, 4].map((i) => <div key={i} style={{ height: 200 }} className="skeleton" />)}
        </div>
      ) : (
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))",
            gap: 1,
            background: tools.length > 0 ? "var(--cds-border-subtle-00)" : "transparent",
          }}
        >
          {tools.map((tool) => (
            <div
              key={tool.id}
              style={{
                background: "var(--cds-layer-01)",
                padding: "var(--spacing-05)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
                transition: "background var(--transition)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--cds-layer-hover-01)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--cds-layer-01)")}
            >
              {/* Tool header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h3 style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
                    {tool.name}
                  </h3>
                  <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.6875rem", color: "var(--cds-text-helper)", marginTop: 2 }}>
                    {tool.id}
                  </p>
                </div>
                {getCategoryTag(tool.category)}
              </div>

              <p style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", lineHeight: 1.5 }}>
                {tool.description}
              </p>

              {/* Details */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 8,
                  padding: "8px 0",
                  borderTop: "1px solid var(--cds-border-subtle-00)",
                  borderBottom: "1px solid var(--cds-border-subtle-00)",
                }}
              >
                <div>
                  <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>HITL</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", display: "flex", alignItems: "center", gap: 4 }}>
                    {tool.requires_approval
                      ? <><UserCheck className="w-3.5 h-3.5" style={{ color: "#d4bbff" }} /> Required</>
                      : <><Check className="w-3.5 h-3.5" style={{ color: "var(--cds-support-success)" }} /> Auto</>
                    }
                  </span>
                </div>
                <div>
                  <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>Isolation</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", display: "flex", alignItems: "center", gap: 4 }}>
                    {tool.sandbox_required
                      ? <><Terminal className="w-3.5 h-3.5" style={{ color: "var(--cds-support-warning)" }} /> Docker</>
                      : <><Cpu className="w-3.5 h-3.5" style={{ color: "var(--cds-link-primary)" }} /> Inline</>
                    }
                  </span>
                </div>
                <div>
                  <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>Timeout</span>
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
                    {tool.timeout_seconds}s
                  </span>
                </div>
              </div>

              {/* Schema */}
              <div>
                <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
                  JSON Schema
                </p>
                <pre
                  style={{
                    background: "var(--cds-layer-02)",
                    border: "1px solid var(--cds-border-subtle-00)",
                    padding: "8px 10px",
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: "0.6875rem",
                    color: "var(--cds-link-primary)",
                    overflowX: "auto",
                    maxHeight: 100,
                  }}
                >
                  {JSON.stringify(tool.parameters_schema, null, 2)}
                </pre>
              </div>

              {tool.category !== "builtin" && (
                <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 8, borderTop: "1px solid var(--cds-border-subtle-00)" }}>
                  <button
                    onClick={() => handleDelete(tool.id)}
                    className="btn btn-ghost btn-icon"
                    title="Delete tool"
                    style={{ color: "var(--cds-support-error)" }}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          ))}

          {tools.length === 0 && (
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
              No custom tools registered.
            </div>
          )}
        </section>
      )}

      {/* ── Register Tool Modal ──────────────────────────────────────── */}
      {isOpen && (
        <div className="cds-modal-overlay animate-fade-in">
          <div className="cds-modal" style={{ maxWidth: 580 }}>
            <div className="cds-modal-header">
              <h2 className="cds-modal-title">Register Custom Tool</h2>
              <button onClick={() => setIsOpen(false)} className="cds-modal-close">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreate}>
              <div className="cds-modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <label className="input-label">Tool ID (name)</label>
                    <input
                      type="text" required className="input"
                      placeholder="my_helper_tool"
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                      value={name} onChange={(e) => setName(e.target.value)}
                    />
                    <p className="input-helper">Python identifier (a-z, _, 0-9)</p>
                  </div>
                  <div>
                    <label className="input-label">Category</label>
                    <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
                      <option value="custom">Custom Code (Python)</option>
                      <option value="mcp">MCP Protocol Server</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="input-label">Description</label>
                  <textarea
                    required rows={2} className="input"
                    placeholder="When should the agent use this tool?"
                    value={description} onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                {category === "custom" && (
                  <div>
                    <label className="input-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Code className="w-3.5 h-3.5" style={{ color: "var(--cds-link-primary)" }} />
                      Python Source Code
                    </label>
                    <textarea
                      required rows={6} className="input"
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", background: "var(--cds-layer-02)" }}
                      value={functionCode} onChange={(e) => setFunctionCode(e.target.value)}
                    />
                  </div>
                )}

                {category === "mcp" && (
                  <div>
                    <label className="input-label">MCP Server URL</label>
                    <input
                      type="text" required className="input"
                      placeholder="http://localhost:3011/sse"
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                      value={mcpServerUrl} onChange={(e) => setMcpServerUrl(e.target.value)}
                    />
                  </div>
                )}

                <div>
                  <label className="input-label">JSON Parameters Schema</label>
                  <textarea
                    required rows={5} className="input"
                    style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", background: "var(--cds-layer-02)" }}
                    value={parametersSchemaStr} onChange={(e) => setParametersSchemaStr(e.target.value)}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, paddingTop: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input
                      type="checkbox" id="approval"
                      style={{ accentColor: "var(--cds-interactive)", width: 16, height: 16 }}
                      checked={requiresApproval} onChange={(e) => setRequiresApproval(e.target.checked)}
                    />
                    <label htmlFor="approval" style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", cursor: "pointer" }}>
                      HITL Approval
                    </label>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input
                      type="checkbox" id="sandbox"
                      style={{ accentColor: "var(--cds-interactive)", width: 16, height: 16 }}
                      checked={sandboxRequired} disabled={category === "mcp"}
                      onChange={(e) => setSandboxRequired(e.target.checked)}
                    />
                    <label htmlFor="sandbox" style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", cursor: "pointer" }}>
                      Sandbox
                    </label>
                  </div>
                  <div>
                    <label className="input-label">Timeout (s)</label>
                    <input
                      type="number" min="1" max="300" className="input"
                      style={{ fontSize: "0.75rem" }}
                      value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(parseInt(e.target.value))}
                    />
                  </div>
                </div>
              </div>

              <div className="cds-modal-footer">
                <button type="button" onClick={() => setIsOpen(false)} className="btn btn-ghost">Cancel</button>
                <button type="submit" disabled={submitting} className="btn btn-primary">
                  {submitting ? "Registering…" : "Add to Registry"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
