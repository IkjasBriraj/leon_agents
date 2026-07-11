"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  Panel,
} from "@xyflow/react";
import {
  Save,
  Play,
  ArrowLeft,
  Bot,
  Wrench,
  GitFork,
  UserCheck,
  Database,
  Code,
  AlertCircle,
  HelpCircle,
  Cpu,
  Trash2,
} from "lucide-react";

import { useWorkflowStore } from "@/store/workflowStore";
import { useRunStore } from "@/store/runStore";
import { nodeTypesMap } from "@/components/flow/NodeTypes";
import { api, type Agent } from "@/lib/api";

export default function WorkflowBuilderPage({
  params: paramsPromise,
}: {
  params: Promise<{ id: string }>;
}) {
  const params = use(paramsPromise);
  const router = useRouter();
  const workflowId = params.id;

  const {
    loadWorkflow, saveWorkflow,
    nodes, edges, workflowName, workflowDescription,
    onNodesChange, onEdgesChange, onConnect,
    addNode, deleteNode, selectedNodeId, selectNode,
    updateNodeConfig, updateNodeLabel,
    validation, isSaving, isLoading,
  } = useWorkflowStore();

  const { triggerRun, isExecuting } = useRunStore();

  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);
  const [showInputModal, setShowInputModal] = useState(false);
  const [runInput, setRunInput] = useState('{\n  "message": "Write a python script that sums squares of first 10 digits"\n}');

  useEffect(() => {
    loadWorkflow(workflowId);
    api.get<any>("/agents")
      .then((data) => setAvailableAgents(data.items))
      .catch((err) => console.error("Failed to load agents", err));
  }, [workflowId, loadWorkflow]);

  const handleSave = async () => {
    try { await saveWorkflow(); }
    catch { alert("Failed to save workflow"); }
  };

  const handleRun = async () => {
    try {
      let parsedInput = {};
      try { parsedInput = JSON.parse(runInput); }
      catch { alert("Invalid input JSON"); return; }
      setShowInputModal(false);
      const runId = await triggerRun(workflowId, parsedInput);
      router.push(`/dashboard/workflows/${workflowId}/runs/${runId}`);
    } catch (err: any) {
      alert(err.message || "Failed to trigger run");
    }
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  /* ── Node toolbox button config ──────────────────────────────────── */
  const nodeButtons = [
    { type: "agent", icon: <Bot className="w-5 h-5" />, label: "Agent", color: "var(--node-agent)" },
    { type: "tool", icon: <Wrench className="w-5 h-5" />, label: "Tool", color: "var(--node-tool)" },
    { type: "condition", icon: <GitFork className="w-5 h-5" />, label: "Condition", color: "var(--node-condition)" },
    { type: "hitl_gate", icon: <UserCheck className="w-5 h-5" />, label: "HITL", color: "var(--node-hitl)" },
    { type: "memory_read", icon: <Database className="w-5 h-5" />, label: "Memory", color: "var(--node-memory)" },
    { type: "code", icon: <Code className="w-5 h-5" />, label: "Code", color: "var(--node-code)" },
  ];

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--cds-background)",
        color: "var(--cds-text-primary)",
        overflow: "hidden",
      }}
    >
      {/* ── Builder Topbar ───────────────────────────────────────────── */}
      <header
        className="app-topbar"
        style={{ justifyContent: "space-between", padding: "0 var(--spacing-05)" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => router.push("/dashboard/workflows")} className="btn btn-ghost btn-icon" title="Back to library">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)", lineHeight: 1.2 }}>
              {workflowName}
            </h1>
            <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)" }}>
              {workflowDescription || "Visual graph canvas"}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {validation && !validation.isValid && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 10px",
                background: "var(--cds-notification-warning-bg)",
                border: "1px solid rgba(241,194,27,0.25)",
                color: "var(--cds-support-warning)",
                fontSize: "0.75rem",
                fontWeight: 600,
              }}
            >
              <AlertCircle className="w-3.5 h-3.5" /> Graph Invalid
            </div>
          )}
          <button onClick={handleSave} disabled={isSaving} className="btn btn-ghost btn-sm">
            <Save className={`w-4 h-4 ${isSaving ? "animate-pulse" : ""}`} />
            {isSaving ? "Saving…" : "Save"}
          </button>
          <button onClick={() => setShowInputModal(true)} disabled={isExecuting} className="btn btn-primary btn-sm">
            <Play className="w-4 h-4" />
            {isExecuting ? "Running…" : "Run Pipeline"}
          </button>
        </div>
      </header>

      {/* ── Editor body ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Node toolbox */}
        <aside
          style={{
            width: 64,
            background: "var(--cds-layer-01)",
            borderRight: "1px solid var(--cds-border-subtle-00)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "var(--spacing-04) 0",
            gap: 8,
          }}
        >
          <span
            style={{
              fontSize: "0.5625rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--cds-text-helper)",
              marginBottom: 4,
            }}
          >
            Blocks
          </span>
          {nodeButtons.map((nb) => (
            <button
              key={nb.type}
              onClick={() => addNode(nb.type as any, { x: 250, y: 150 })}
              title={`Add ${nb.label}`}
              style={{
                width: 40, height: 40,
                background: `color-mix(in srgb, ${nb.color} 12%, transparent)`,
                border: `1px solid color-mix(in srgb, ${nb.color} 30%, transparent)`,
                color: nb.color,
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer",
                transition: "background var(--transition)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = `color-mix(in srgb, ${nb.color} 22%, transparent)`)}
              onMouseLeave={(e) => (e.currentTarget.style.background = `color-mix(in srgb, ${nb.color} 12%, transparent)`)}
            >
              {nb.icon}
            </button>
          ))}
        </aside>

        {/* Canvas */}
        <div style={{ flex: 1, height: "100%", position: "relative" }}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            nodeTypes={nodeTypesMap}
            onNodeClick={(_, node) => selectNode(node.id)}
            onPaneClick={() => selectNode(null)}
            fitView
          >
            <Background variant={BackgroundVariant.Dots} color="rgba(99, 120, 180, 0.08)" gap={20} />
            <Controls />
            <MiniMap style={{ background: "var(--cds-layer-01)", border: "1px solid var(--cds-border-subtle-00)" }} />

            <Panel position="top-left">
              <div
                style={{
                  background: "var(--cds-layer-01)",
                  border: "1px solid var(--cds-border-subtle-00)",
                  padding: "var(--spacing-04)",
                  maxWidth: 260,
                  pointerEvents: "none",
                }}
              >
                <p
                  style={{
                    fontSize: "0.625rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: "var(--cds-link-primary)",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 6,
                  }}
                >
                  <Cpu className="w-3 h-3" /> Graph Validation
                </p>
                {validation ? (
                  <>
                    <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-secondary)", lineHeight: 1.5 }}>
                      {validation.isValid ? "✅ All checks passed." : "❌ Validation issues:"}
                    </p>
                    <ul style={{ fontSize: "0.6875rem", color: "var(--cds-support-error)", listStyle: "disc", paddingLeft: 14, marginTop: 4 }}>
                      {validation.errors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                    <ul style={{ fontSize: "0.6875rem", color: "var(--cds-support-warning)", listStyle: "disc", paddingLeft: 14, marginTop: 4 }}>
                      {validation.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </>
                ) : (
                  <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)" }}>No validation data.</p>
                )}
              </div>
            </Panel>
          </ReactFlow>
        </div>

        {/* Properties Panel */}
        <aside
          style={{
            width: 300,
            background: "var(--cds-layer-01)",
            borderLeft: "1px solid var(--cds-border-subtle-00)",
            padding: "var(--spacing-05)",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          {selectedNode ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div style={{ paddingBottom: 12, borderBottom: "1px solid var(--cds-border-subtle-00)" }}>
                <p style={{ fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--cds-text-helper)", marginBottom: 4 }}>
                  Properties Panel
                </p>
                <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)", textTransform: "capitalize" }}>
                  {selectedNode.type} Node
                </h2>
              </div>

              <div>
                <label className="input-label">Node Title</label>
                <input
                  type="text" className="input"
                  value={selectedNode.data.label}
                  onChange={(e) => updateNodeLabel(selectedNode.id, e.target.value)}
                />
              </div>

              {/* Dynamic node config */}
              {selectedNode.type === "agent" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label className="input-label">Agent Persona</label>
                    <select className="input" value={selectedNode.data.config?.agent_id || ""} onChange={(e) => updateNodeConfig(selectedNode.id, { agent_id: e.target.value })}>
                      <option value="">— select agent —</option>
                      {availableAgents.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.model_name})</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="input-label">System Prompt Override</label>
                    <textarea
                      rows={4} className="input"
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                      placeholder="Optional. Overrides default prompt."
                      value={selectedNode.data.config?.system_prompt_override || ""}
                      onChange={(e) => updateNodeConfig(selectedNode.id, { system_prompt_override: e.target.value })}
                    />
                  </div>
                </div>
              )}

              {selectedNode.type === "tool" && (
                <div>
                  <label className="input-label">Execution Tool</label>
                  <select className="input" value={selectedNode.data.config?.tool_name || "web_search"} onChange={(e) => updateNodeConfig(selectedNode.id, { tool_name: e.target.value })}>
                    <option value="web_search">web_search</option>
                    <option value="python_repl">python_repl</option>
                    <option value="calculator">calculator</option>
                    <option value="http_request">http_request</option>
                  </select>
                </div>
              )}

              {selectedNode.type === "condition" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label className="input-label">State Field Path</label>
                    <input
                      type="text" className="input"
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                      placeholder="e.g. context.result"
                      value={selectedNode.data.config?.expression?.field || ""}
                      onChange={(e) => updateNodeConfig(selectedNode.id, { expression: { ...(selectedNode.data.config?.expression || {}), field: e.target.value } })}
                    />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div>
                      <label className="input-label">Operator</label>
                      <select className="input" value={selectedNode.data.config?.expression?.op || "eq"} onChange={(e) => updateNodeConfig(selectedNode.id, { expression: { ...(selectedNode.data.config?.expression || {}), op: e.target.value } })}>
                        <option value="eq">eq</option>
                        <option value="ne">ne</option>
                        <option value="gt">gt</option>
                        <option value="lt">lt</option>
                        <option value="contains">contains</option>
                        <option value="truthy">truthy</option>
                        <option value="falsy">falsy</option>
                      </select>
                    </div>
                    <div>
                      <label className="input-label">Value</label>
                      <input
                        type="text" className="input"
                        style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                        placeholder="match"
                        value={selectedNode.data.config?.expression?.value || ""}
                        onChange={(e) => updateNodeConfig(selectedNode.id, { expression: { ...(selectedNode.data.config?.expression || {}), value: e.target.value } })}
                      />
                    </div>
                  </div>
                </div>
              )}

              {selectedNode.type === "hitl_gate" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label className="input-label">Pause Message</label>
                    <textarea rows={3} className="input" placeholder="Instructions for reviewer…" value={selectedNode.data.config?.message || ""} onChange={(e) => updateNodeConfig(selectedNode.id, { message: e.target.value })} />
                  </div>
                  <div>
                    <label className="input-label">Required Role</label>
                    <select className="input" value={selectedNode.data.config?.approval_roles?.[0] || "member"} onChange={(e) => updateNodeConfig(selectedNode.id, { approval_roles: [e.target.value] })}>
                      <option value="member">member or higher</option>
                      <option value="admin">admin or higher</option>
                      <option value="owner">owner only</option>
                    </select>
                  </div>
                </div>
              )}

              {selectedNode.type === "memory_read" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label className="input-label">Semantic Query</label>
                    <input type="text" className="input" placeholder="e.g. $message" value={selectedNode.data.config?.query || ""} onChange={(e) => updateNodeConfig(selectedNode.id, { query: e.target.value })} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div>
                      <label className="input-label">Top-K</label>
                      <input type="number" className="input" value={selectedNode.data.config?.k || 5} onChange={(e) => updateNodeConfig(selectedNode.id, { k: parseInt(e.target.value) || 5 })} />
                    </div>
                    <div>
                      <label className="input-label">Context Key</label>
                      <input type="text" className="input" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }} value={selectedNode.data.config?.context_key || "retrieved_knowledge"} onChange={(e) => updateNodeConfig(selectedNode.id, { context_key: e.target.value })} />
                    </div>
                  </div>
                </div>
              )}

              {selectedNode.type === "code" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label className="input-label">Language</label>
                    <select className="input" value={selectedNode.data.config?.language || "python"} onChange={(e) => updateNodeConfig(selectedNode.id, { language: e.target.value })}>
                      <option value="python">python (3.11)</option>
                      <option value="javascript">javascript (Node.js)</option>
                    </select>
                  </div>
                  <div>
                    <label className="input-label">Source Code</label>
                    <textarea rows={6} className="input" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", lineHeight: 1.5 }} placeholder="Write block code here…" value={selectedNode.data.config?.source_code || ""} onChange={(e) => updateNodeConfig(selectedNode.id, { source_code: e.target.value })} />
                  </div>
                </div>
              )}

              <button onClick={() => deleteNode(selectedNode.id)} className="btn btn-danger" style={{ marginTop: 8 }}>
                <Trash2 className="w-4 h-4" /> Remove Block
              </button>
            </div>
          ) : (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", color: "var(--cds-text-helper)", padding: "var(--spacing-05)" }}>
              <HelpCircle className="w-8 h-8 mb-8" style={{ opacity: 0.4 }} />
              <p style={{ fontSize: "0.75rem" }}>
                Click a node on the canvas to configure its properties.
              </p>
            </div>
          )}
        </aside>
      </div>

      {/* ── Run Input Modal ───────────────────────────────────────────── */}
      {showInputModal && (
        <div className="cds-modal-overlay animate-fade-in">
          <div className="cds-modal" style={{ maxWidth: 460 }}>
            <div className="cds-modal-header">
              <h2 className="cds-modal-title">Execute Workflow</h2>
            </div>
            <div className="cds-modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ fontSize: "0.875rem", color: "var(--cds-text-secondary)" }}>
                Provide input variables as a JSON object.
              </p>
              <div>
                <label className="input-label" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>input_data (JSON)</label>
                <textarea
                  rows={6} className="input"
                  style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                  value={runInput} onChange={(e) => setRunInput(e.target.value)}
                />
              </div>
            </div>
            <div className="cds-modal-footer">
              <button type="button" onClick={() => setShowInputModal(false)} className="btn btn-ghost">Cancel</button>
              <button type="button" onClick={handleRun} className="btn btn-primary">Trigger Execution</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
