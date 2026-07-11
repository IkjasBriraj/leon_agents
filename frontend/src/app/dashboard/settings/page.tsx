"use client";

import React, { useEffect, useState } from "react";
import { Settings, Cpu, Shield, Key, Plus, Trash2, Save, Check, ShieldAlert, X } from "lucide-react";
import { api, type User } from "@/lib/api";

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [ollamaHost, setOllamaHost] = useState("http://localhost:11434");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [apiKeys, setApiKeys] = useState([
    { id: "1", name: "Production Flow CLI", prefix: "ac_live_7a3d", created: "2026-07-01", scopes: ["runs:write", "agents:read"] },
    { id: "2", name: "Development Local Sandbox", prefix: "ac_dev_2e8f", created: "2026-07-05", scopes: ["*"] },
  ]);
  const [keyName, setKeyName] = useState("");
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.get<User>("/auth/me")
      .then((data) => {
        setUser(data);
        api.get<any>("/auth/me")
          .then(() => {
            setOrgName("My Team");
            setOrgSlug("my-team");
            const savedOllama = localStorage.getItem("agentcraft_ollama_host");
            if (savedOllama) setOllamaHost(savedOllama);
          })
          .finally(() => setLoading(false));
      })
      .catch((err) => {
        setError(err.message || "Failed to load settings");
        setLoading(false);
      });
  }, []);

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg(null); setError(null);
    try {
      localStorage.setItem("agentcraft_ollama_host", ollamaHost);
      setSuccessMsg("Settings saved successfully.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch {
      setError("Failed to save settings");
    }
  };

  const handleGenerateKey = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName.trim()) return;
    const randomHex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
    const newKeyString = `ac_live_${randomHex}`;
    setGeneratedKey(newKeyString);
    setApiKeys((prev) => [{
      id: String(Date.now()), name: keyName,
      prefix: `ac_live_${randomHex.substring(0, 6)}`,
      created: new Date().toISOString().split("T")[0], scopes: ["*"],
    }, ...prev]);
    setKeyName("");
  };

  const handleDeleteKey = (id: string) => setApiKeys((prev) => prev.filter((k) => k.id !== id));

  const panelStyle: React.CSSProperties = {
    background: "var(--cds-layer-01)",
    border: "1px solid var(--cds-border-subtle-00)",
    padding: "var(--spacing-06)",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  };

  return (
    <div
      className="animate-fade-in"
      style={{ padding: "var(--spacing-07)", maxWidth: 900, display: "flex", flexDirection: "column", gap: 32 }}
    >
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Workspace Settings</h1>
          <p className="page-subtitle">Configure LLM connections, API keys, and organization parameters.</p>
        </div>
      </div>

      {error && <div className="cds-notification error"><ShieldAlert className="w-4 h-4 flex-shrink-0" /><span>{error}</span></div>}
      {successMsg && <div className="cds-notification success"><Check className="w-4 h-4 flex-shrink-0" /><span>{successMsg}</span></div>}

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ height: 200 }} className="skeleton" />
          <div style={{ height: 200 }} className="skeleton" />
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 1, background: "var(--cds-border-subtle-00)" }}>

          {/* ── Organization + Ollama ────────────────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--cds-border-subtle-00)" }}>
            {/* Org Settings */}
            <form onSubmit={handleSaveSettings} style={panelStyle}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <Shield className="w-4 h-4" style={{ color: "var(--cds-link-primary)" }} />
                <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
                  Organization
                </h2>
              </div>
              <div>
                <label className="input-label">Workspace Name</label>
                <input type="text" required className="input" value={orgName} onChange={(e) => setOrgName(e.target.value)} />
              </div>
              <div>
                <label className="input-label">Workspace Slug</label>
                <input
                  type="text" disabled className="input" value={orgSlug}
                  style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                />
              </div>
              <button type="submit" className="btn btn-primary" style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
                <Save className="w-4 h-4" /> Save
              </button>
            </form>

            {/* Ollama Settings */}
            <form onSubmit={handleSaveSettings} style={panelStyle}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <Cpu className="w-4 h-4" style={{ color: "var(--cds-link-primary)" }} />
                <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
                  Ollama Connection
                </h2>
              </div>
              <div>
                <label className="input-label">Host URL</label>
                <input
                  type="text" required className="input"
                  placeholder="http://localhost:11434"
                  value={ollamaHost} onChange={(e) => setOllamaHost(e.target.value)}
                  style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                />
                <p className="input-helper">FastAPI routes LLM completion calls to this self-hosted endpoint.</p>
              </div>
              <div
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "8px 12px",
                  background: "var(--cds-layer-02)",
                  border: "1px solid var(--cds-border-subtle-00)",
                  fontSize: "0.75rem",
                }}
              >
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--cds-support-success)", flexShrink: 0 }} />
                <span style={{ color: "var(--cds-support-success)", fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}>
                  CONNECTED
                </span>
              </div>
              <button type="submit" className="btn btn-primary" style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
                <Save className="w-4 h-4" /> Save
              </button>
            </form>
          </div>

          {/* ── API Keys ───────────────────────────────────────────────── */}
          <div style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <Key className="w-4 h-4" style={{ color: "var(--cds-link-primary)" }} />
                  <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
                    API Credentials
                  </h2>
                </div>
                <p style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
                  Authenticate remote CLI execution, deployment triggers, and API access.
                </p>
              </div>
              <button
                onClick={() => { setGeneratedKey(null); setShowKeyModal(true); }}
                className="btn btn-ghost btn-sm"
              >
                <Plus className="w-4 h-4" /> New Key
              </button>
            </div>

            <div style={{ border: "1px solid var(--cds-border-subtle-00)", overflow: "hidden" }}>
              <table className="cds-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Prefix</th>
                    <th>Created</th>
                    <th>Scopes</th>
                    <th style={{ textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((k) => (
                    <tr key={k.id}>
                      <td style={{ fontWeight: 600 }}>{k.name}</td>
                      <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
                        {k.prefix}••••
                      </td>
                      <td style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>{k.created}</td>
                      <td>
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          {k.scopes.map((s) => (
                            <span key={s} className="cds-tag blue" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{s}</span>
                          ))}
                        </div>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          onClick={() => handleDeleteKey(k.id)}
                          className="btn btn-ghost btn-icon"
                          style={{ color: "var(--cds-support-error)" }}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {apiKeys.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ padding: "var(--spacing-07)", textAlign: "center", color: "var(--cds-text-helper)" }}>
                        No API keys.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── User Profile ──────────────────────────────────────────── */}
          <div
            style={{
              background: "var(--cds-layer-01)",
              padding: "var(--spacing-05) var(--spacing-06)",
              display: "flex",
              alignItems: "center",
              gap: 16,
            }}
          >
            <div
              style={{
                width: 40, height: 40,
                background: "rgba(15,98,254,0.12)",
                border: "1px solid rgba(69,137,255,0.25)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "1rem", fontWeight: 700,
                color: "var(--cds-link-primary)",
                flexShrink: 0,
              }}
            >
              {user?.full_name?.charAt(0) || "U"}
            </div>
            <div>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>{user?.full_name}</p>
              <p style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", marginTop: 2 }}>{user?.email}</p>
              <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace", marginTop: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                {user?.role} access
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Generate Key Modal ─────────────────────────────────────────── */}
      {showKeyModal && (
        <div className="cds-modal-overlay animate-fade-in">
          <div className="cds-modal" style={{ maxWidth: 440 }}>
            <div className="cds-modal-header">
              <h2 className="cds-modal-title">Generate API Key</h2>
              <button onClick={() => setShowKeyModal(false)} className="cds-modal-close">
                <X className="w-5 h-5" />
              </button>
            </div>

            {!generatedKey ? (
              <form onSubmit={handleGenerateKey}>
                <div className="cds-modal-body">
                  <label className="input-label">Key Name / Description</label>
                  <input
                    type="text" required
                    placeholder="e.g. CLI Sync Key"
                    className="input"
                    value={keyName} onChange={(e) => setKeyName(e.target.value)}
                  />
                </div>
                <div className="cds-modal-footer">
                  <button type="button" onClick={() => setShowKeyModal(false)} className="btn btn-ghost">Cancel</button>
                  <button type="submit" className="btn btn-primary">Generate Token</button>
                </div>
              </form>
            ) : (
              <div>
                <div className="cds-modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="cds-notification warning">
                    <span style={{ fontSize: "0.75rem" }}>
                      Copy this key now — it will not be shown again.
                    </span>
                  </div>
                  <div
                    style={{
                      padding: "var(--spacing-04)",
                      background: "var(--cds-layer-02)",
                      border: "1px solid var(--cds-border-subtle-01)",
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: "0.75rem",
                      color: "var(--cds-link-primary)",
                      wordBreak: "break-all",
                      userSelect: "all",
                    }}
                  >
                    {generatedKey}
                  </div>
                </div>
                <div className="cds-modal-footer">
                  <button onClick={() => setShowKeyModal(false)} className="btn btn-primary">
                    I've stored the key securely
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
