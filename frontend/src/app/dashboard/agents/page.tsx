"use client";

import React, { useEffect, useState } from "react";
import { Bot, Plus, Sliders, Tag, Trash2, Cpu, X } from "lucide-react";
import { api, type Agent } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [modelName, setModelName] = useState("llama3.2");
  const [temperature, setTemperature] = useState(0.7);
  const [systemPrompt, setSystemPrompt] = useState("You are an expert agentic assistant.");
  const [tagsInput, setTagsInput] = useState("");

  const loadAgents = () => {
    setLoading(true);
    api.get<any>("/agents")
      .then((data) => setAgents(data.items))
      .catch((err) => setError(err.message || "Failed to load agents"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadAgents(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/agents", {
        name,
        description: description || null,
        model_provider: "ollama",
        model_name: modelName,
        temperature,
        system_prompt: systemPrompt,
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setIsOpen(false);
      setName(""); setDescription(""); setTemperature(0.7);
      setSystemPrompt("You are an expert agentic assistant."); setTagsInput("");
      loadAgents();
    } catch (err: any) {
      setError(err.message || "Failed to create agent");
    }
  };

  const handleArchive = async (id: string) => {
    if (!confirm("Archive this agent?")) return;
    try {
      await api.delete(`/agents/${id}`);
      loadAgents();
    } catch (err: any) {
      alert(err.message || "Failed to archive agent");
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "var(--spacing-07)", display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ height: 28, width: 200 }} className="skeleton" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 1, background: "var(--cds-border-subtle-00)" }}>
          {[1, 2, 3].map((i) => <div key={i} style={{ height: 240, background: "var(--cds-layer-01)" }} className="skeleton" />)}
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
          <h1 className="page-title">Agent Registry</h1>
          <p className="page-subtitle">Configure reasoning personas and models for your workflows.</p>
        </div>
        <button onClick={() => setIsOpen(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Deploy Agent
        </button>
      </div>

      {error && (
        <div className="cds-notification error">
          <span>{error}</span>
        </div>
      )}

      {/* Agent cards */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 1,
          background: agents.length > 0 ? "var(--cds-border-subtle-00)" : "transparent",
        }}
      >
        {agents.map((agent) => (
          <div
            key={agent.id}
            style={{
              background: "var(--cds-layer-01)",
              padding: "var(--spacing-05)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: 220,
              transition: "background var(--transition)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--cds-layer-hover-01)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "var(--cds-layer-01)")}
          >
            <div>
              {/* Agent header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    className="cds-icon-box"
                    style={{ background: "rgba(69,137,255,0.10)", border: "1px solid rgba(69,137,255,0.20)", color: "var(--cds-link-primary)" }}
                  >
                    <Bot className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {agent.name}
                    </h3>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
                      <Cpu className="w-3 h-3" style={{ color: "var(--cds-text-helper)" }} />
                      <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace" }}>
                        {agent.model_provider}/{agent.model_name}
                      </span>
                    </div>
                  </div>
                </div>
                <span className={`status-badge status-${agent.status === "archived" ? "archived" : "active"}`}>
                  {agent.status}
                </span>
              </div>

              <p style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", lineHeight: 1.5, marginBottom: 12, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                {agent.description || "No description provided."}
              </p>

              {/* Tags */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 12 }}>
                {agent.tags.map((tag) => (
                  <span key={tag} className="cds-tag blue">
                    <Tag className="w-2.5 h-2.5" /> {tag}
                  </span>
                ))}
                {agent.tags.length === 0 && (
                  <span style={{ fontSize: "0.75rem", color: "var(--cds-text-helper)" }}>No tags</span>
                )}
              </div>
            </div>

            {/* Footer */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                paddingTop: 12,
                borderTop: "1px solid var(--cds-border-subtle-00)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
                <Sliders className="w-3.5 h-3.5" /> Temp: {agent.temperature}
              </div>
              <button
                onClick={() => handleArchive(agent.id)}
                className="btn btn-ghost btn-icon"
                title="Archive agent"
                style={{ color: "var(--cds-support-error)" }}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}

        {agents.length === 0 && (
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
            No agents found. Click "Deploy Agent" to create your first reasoning persona.
          </div>
        )}
      </section>

      {/* ── Deploy Agent Modal ───────────────────────────────────────── */}
      {isOpen && (
        <div className="cds-modal-overlay animate-fade-in">
          <div className="cds-modal" style={{ maxWidth: 500 }}>
            <div className="cds-modal-header">
              <h2 className="cds-modal-title">Deploy New Agent</h2>
              <button onClick={() => setIsOpen(false)} className="cds-modal-close">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreate}>
              <div className="cds-modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label className="input-label">Agent Name</label>
                  <input
                    type="text" required className="input"
                    placeholder="e.g. Code Reviewer"
                    value={name} onChange={(e) => setName(e.target.value)}
                  />
                </div>

                <div>
                  <label className="input-label">Description</label>
                  <textarea
                    className="input" placeholder="Summarize what this agent does…"
                    value={description} onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <label className="input-label">Ollama Model</label>
                    <select className="input" value={modelName} onChange={(e) => setModelName(e.target.value)}>
                      <option value="llama3.2">llama3.2 (3B)</option>
                      <option value="llama3">llama3 (8B)</option>
                      <option value="mistral">mistral (7B)</option>
                      <option value="codellama">codellama (7B)</option>
                      <option value="phi3">phi3 (3.8B)</option>
                    </select>
                  </div>
                  <div>
                    <label className="input-label">Temperature: {temperature}</label>
                    <input
                      type="range" min="0" max="1.5" step="0.1"
                      className="w-full mt-2"
                      style={{ accentColor: "var(--cds-interactive)" }}
                      value={temperature} onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    />
                  </div>
                </div>

                <div>
                  <label className="input-label">System Prompt</label>
                  <textarea
                    required rows={4}
                    className="input"
                    style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                    placeholder="Instructions for the agent's behavior…"
                    value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)}
                  />
                </div>

                <div>
                  <label className="input-label">Tags (comma-separated)</label>
                  <input
                    type="text" className="input"
                    placeholder="e.g. engineering, search, review"
                    value={tagsInput} onChange={(e) => setTagsInput(e.target.value)}
                  />
                </div>
              </div>

              <div className="cds-modal-footer">
                <button type="button" onClick={() => setIsOpen(false)} className="btn btn-ghost">Cancel</button>
                <button type="submit" className="btn btn-primary">Deploy</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
