"use client";

import React, { useEffect, useState } from "react";
import { Database, Search, Plus, Tag, Calendar, ShieldAlert, Cpu, Trash2, X } from "lucide-react";
import { api, type Memory, type MemorySearchResult } from "@/lib/api";

export default function MemoryExplorerPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [isSearching, setIsSearching] = useState(false);

  const [isOpen, setIsOpen] = useState(false);
  const [content, setContent] = useState("");
  const [memoryType, setMemoryType] = useState("semantic");
  const [tagsInput, setTagsInput] = useState("");
  const [importance, setImportance] = useState(0.7);
  const [submitting, setSubmitting] = useState(false);

  const loadMemories = () => {
    setLoading(true); setError(null);
    const params: any = { limit: 50 };
    if (selectedType !== "all") params.memory_type = selectedType;
    api.get<Memory[]>("/memory", { params })
      .then((data) => { setMemories(data); setSearchResults([]); })
      .catch((err) => setError(err.message || "Failed to load memories"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (searchQuery.trim() === "") loadMemories();
  }, [selectedType, searchQuery]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) { loadMemories(); return; }
    setIsSearching(true); setError(null);
    try {
      const results = await api.post<MemorySearchResult[]>("/memory/search", {
        query: searchQuery,
        memory_type: selectedType === "all" ? null : selectedType,
        limit: 10,
      });
      setSearchResults(results);
    } catch (err: any) {
      setError(err.message || "Vector search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    setSubmitting(true); setError(null);
    try {
      await api.post("/memory", {
        memory_type: memoryType, content,
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
        importance, metadata: {},
      });
      setIsOpen(false); setContent(""); setTagsInput(""); setImportance(0.7);
      if (searchQuery.trim() === "") loadMemories();
      else { const ev = { preventDefault: () => {} } as React.FormEvent; handleSearch(ev); }
    } catch (err: any) {
      setError(err.message || "Failed to ingest memory");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this memory?")) return;
    try {
      await api.delete(`/memory/${id}`);
      if (searchQuery.trim() === "") loadMemories();
      else setSearchResults((prev) => prev.filter((r) => r.memory.id !== id));
    } catch (err: any) {
      alert(err.message || "Failed to delete memory");
    }
  };

  const getImportanceTag = (score: number) => {
    if (score >= 0.8) return <span className="cds-tag red">High {score.toFixed(1)}</span>;
    if (score >= 0.5) return <span className="cds-tag yellow">Med {score.toFixed(1)}</span>;
    return <span className="cds-tag blue">Low {score.toFixed(1)}</span>;
  };

  const getMemoryTypeTag = (type: string) => {
    switch (type) {
      case "episodic": return <span className="cds-tag blue">Episodic</span>;
      case "semantic": return <span className="cds-tag green">Semantic</span>;
      case "profile": return <span className="cds-tag purple">Profile</span>;
      default: return <span className="cds-tag warm-gray">{type}</span>;
    }
  };

  const displayList = searchQuery.trim() !== ""
    ? searchResults.map((r) => ({ ...r.memory, _score: r.score }))
    : memories.map((m) => ({ ...m, _score: undefined as number | undefined }));

  return (
    <div
      className="animate-fade-in"
      style={{ padding: "var(--spacing-07)", maxWidth: 1100, display: "flex", flexDirection: "column", gap: 32 }}
    >
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Memory Explorer</h1>
          <p className="page-subtitle">Inspect, search, and manage episodic traces, semantic facts, and agent profiles.</p>
        </div>
        <button onClick={() => setIsOpen(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Ingest Facts
        </button>
      </div>

      {error && (
        <div className="cds-notification error">
          <ShieldAlert className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search + filter bar */}
      <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
          <div style={{ position: "relative", flex: 1 }}>
            <Search
              className="w-4 h-4"
              style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--cds-text-placeholder)", pointerEvents: "none" }}
            />
            <input
              type="text"
              placeholder="Search memories via semantic vector space…"
              className="input"
              style={{ paddingLeft: 36 }}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button type="submit" disabled={isSearching} className="btn btn-primary" style={{ minWidth: 120 }}>
            {isSearching ? "Searching…" : "Vector Search"}
          </button>
        </form>

        {/* Type filter pills */}
        <div style={{ display: "flex", gap: 1, background: "var(--cds-border-subtle-00)" }}>
          {["all", "semantic", "episodic", "profile"].map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              style={{
                padding: "6px 16px",
                fontSize: "0.75rem",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.02em",
                background: selectedType === type ? "var(--cds-button-primary)" : "var(--cds-layer-01)",
                color: selectedType === type ? "var(--cds-text-on-color)" : "var(--cds-text-secondary)",
                border: "none",
                cursor: "pointer",
                transition: "background var(--transition), color var(--transition)",
              }}
            >
              {type}
            </button>
          ))}
        </div>
      </section>

      {/* Results */}
      <section>
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 1, background: "var(--cds-border-subtle-00)" }}>
            {[1, 2, 3].map((i) => <div key={i} style={{ height: 120 }} className="skeleton" />)}
          </div>
        ) : (
          <>
            {searchQuery.trim() !== "" && (
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--cds-text-helper)", marginBottom: 12, padding: "0 2px" }}>
                <span>{searchResults.length} semantic match{searchResults.length !== 1 ? "es" : ""}</span>
                <span>sorted by cosine similarity</span>
              </div>
            )}

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 1,
                background: displayList.length > 0 ? "var(--cds-border-subtle-00)" : "transparent",
              }}
            >
              {displayList.map((memory) => (
                <div
                  key={memory.id}
                  style={{
                    background: "var(--cds-layer-01)",
                    padding: "var(--spacing-05)",
                    display: "flex",
                    gap: 24,
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                    transition: "background var(--transition)",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--cds-layer-hover-01)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "var(--cds-layer-01)")}
                >
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      {getMemoryTypeTag(memory.memory_type)}
                      {getImportanceTag(memory.importance)}
                      {(memory as any)._score !== undefined && (
                        <span className="cds-tag teal">
                          Relevance {((memory as any)._score * 100).toFixed(0)}%
                        </span>
                      )}
                      {memory.agent_id && (
                        <span className="cds-tag blue" style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <Cpu className="w-3 h-3" /> Agent Linked
                        </span>
                      )}
                    </div>
                    <p style={{ fontSize: "0.875rem", color: "var(--cds-text-primary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                      {memory.content}
                    </p>
                    {memory.tags && memory.tags.length > 0 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <Tag className="w-3 h-3" style={{ color: "var(--cds-text-helper)" }} />
                        {memory.tags.map((t) => (
                          <span key={t} className="cds-tag warm-gray">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", justifyContent: "space-between", gap: 12, flexShrink: 0 }}>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace", display: "block" }}>
                        Accessed {memory.access_count}×
                      </span>
                      <span style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace", display: "block" }}>
                        {new Date(memory.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <button
                      onClick={() => handleDelete(memory.id)}
                      className="btn btn-ghost btn-icon"
                      title="Delete memory"
                      style={{ color: "var(--cds-support-error)" }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}

              {displayList.length === 0 && (
                <div
                  style={{
                    padding: "var(--spacing-09)",
                    textAlign: "center",
                    color: "var(--cds-text-helper)",
                    fontSize: "0.875rem",
                    border: "1px dashed var(--cds-border-subtle-01)",
                  }}
                >
                  {searchQuery.trim() !== ""
                    ? "No matching memories found above threshold."
                    : "No memories stored. Click "Ingest Facts" to load semantic documents."}
                </div>
              )}
            </div>
          </>
        )}
      </section>

      {/* ── Ingest Modal ─────────────────────────────────────────────── */}
      {isOpen && (
        <div className="cds-modal-overlay animate-fade-in">
          <div className="cds-modal" style={{ maxWidth: 520 }}>
            <div className="cds-modal-header">
              <h2 className="cds-modal-title">Ingest Facts into Memory</h2>
              <button onClick={() => setIsOpen(false)} className="cds-modal-close">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleIngest}>
              <div className="cds-modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label className="input-label">Memory Classification</label>
                  <select className="input" value={memoryType} onChange={(e) => setMemoryType(e.target.value)}>
                    <option value="semantic">Semantic (knowledge base, facts, RAG)</option>
                    <option value="profile">Profile (rules, constraints, instructions)</option>
                    <option value="episodic">Episodic (system interactions, events)</option>
                  </select>
                </div>

                <div>
                  <label className="input-label">Content / Document Text</label>
                  <textarea
                    required rows={6} className="input"
                    placeholder="Enter semantic context, system instruction, or fact…"
                    value={content} onChange={(e) => setContent(e.target.value)}
                  />
                </div>

                <div>
                  <label className="input-label">Tags (comma-separated)</label>
                  <input
                    type="text" className="input"
                    placeholder="rule, database, credentials, slack"
                    value={tagsInput} onChange={(e) => setTagsInput(e.target.value)}
                  />
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <label className="input-label" style={{ marginBottom: 0 }}>Importance Weight</label>
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", color: "var(--cds-link-primary)" }}>
                      {importance.toFixed(1)}
                    </span>
                  </div>
                  <input
                    type="range" min="0" max="1" step="0.1"
                    style={{ width: "100%", accentColor: "var(--cds-interactive)" }}
                    value={importance} onChange={(e) => setImportance(parseFloat(e.target.value))}
                  />
                </div>
              </div>

              <div className="cds-modal-footer">
                <button type="button" onClick={() => setIsOpen(false)} className="btn btn-ghost">Cancel</button>
                <button type="submit" disabled={submitting} className="btn btn-primary">
                  {submitting ? "Embedding…" : "Store Fact"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
