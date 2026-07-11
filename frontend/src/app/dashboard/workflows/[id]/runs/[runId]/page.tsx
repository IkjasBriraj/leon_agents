"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  RefreshCw,
  Cpu,
  Clock,
  Coins,
  Bot,
  Wrench,
  GitFork,
  UserCheck,
  Database,
  Code,
  Terminal,
  AlertTriangle,
  Play,
  XCircle,
  Eye,
  CheckCircle,
} from "lucide-react";

import { useRunStore } from "@/store/runStore";
import { api } from "@/lib/api";

export default function TraceDebuggerPage({
  params: paramsPromise,
}: {
  params: Promise<{ id: string; runId: string }>;
}) {
  const params = use(paramsPromise);
  const router = useRouter();
  const { id: workflowId, runId } = params;

  const {
    currentRun, steps, activeStepIndex, activeNodeKey,
    logOutput, streamingToken, isExecuting,
    pendingHitl, loadRun, connectWebSocket, disconnectWebSocket,
    resumeRun, cancelRun, selectStep, reset,
  } = useRunStore();

  const [selectedStepIdx, setSelectedStepIdx] = useState<number | null>(null);
  const [editedStateStr, setEditedStateStr] = useState("");
  const [hitlMessage, setHitlMessage] = useState("");

  useEffect(() => {
    loadRun(runId);
    connectWebSocket(runId);
    return () => { reset(); };
  }, [runId, loadRun, connectWebSocket, reset]);

  useEffect(() => {
    if (pendingHitl) setEditedStateStr(JSON.stringify(pendingHitl.stateSnapshot, null, 2));
  }, [pendingHitl]);

  const handleCancel = async () => {
    if (confirm("Cancel this running pipeline?")) await cancelRun();
  };

  const handleHitlDecision = async (decision: "approve" | "reject") => {
    try {
      let parsedState = undefined;
      if (decision === "approve" && editedStateStr) parsedState = JSON.parse(editedStateStr);
      await resumeRun(decision, parsedState, hitlMessage || undefined);
      setHitlMessage("");
    } catch {
      alert("Invalid JSON format in edited state");
    }
  };

  const currentStepIndex = selectedStepIdx !== null ? selectedStepIdx : steps.length - 1;
  const stepDetail = steps.find((s) => s.step_index === currentStepIndex);

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
      {/* ── Debugger Topbar ──────────────────────────────────────────── */}
      <header
        className="app-topbar"
        style={{ justifyContent: "space-between", padding: "0 var(--spacing-05)" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => router.push(`/dashboard/workflows/${workflowId}/builder`)}
            className="btn btn-ghost btn-icon"
            title="Return to canvas"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h1 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)", lineHeight: 1.2 }}>
                Run Debugger
              </h1>
              <span className={`status-badge status-${currentRun?.status === "paused_hitl" ? "paused" : currentRun?.status || "pending"}`}>
                {currentRun?.status === "paused_hitl" ? "paused (hitl)" : currentRun?.status}
              </span>
            </div>
            <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace", marginTop: 2 }}>
              {runId}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: "0.75rem", color: "var(--cds-text-secondary)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <Clock className="w-3.5 h-3.5" />
              {currentRun?.duration_ms ? `${(currentRun.duration_ms / 1000).toFixed(2)}s` : "—"}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <Cpu className="w-3.5 h-3.5" style={{ color: "#d4bbff" }} />
              {currentRun ? currentRun.total_tokens_in + currentRun.total_tokens_out : 0} tokens
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <Coins className="w-3.5 h-3.5" style={{ color: "var(--cds-support-warning)" }} />
              ${currentRun ? parseFloat(currentRun.total_cost_usd || "0").toFixed(4) : "0.0000"}
            </div>
          </div>

          <button onClick={() => loadRun(runId)} className="btn btn-ghost btn-icon">
            <RefreshCw className="w-4 h-4" />
          </button>

          {isExecuting && (
            <button onClick={handleCancel} className="btn btn-danger btn-sm">
              <XCircle className="w-4 h-4" /> Cancel
            </button>
          )}
        </div>
      </header>

      {/* ── Debugger body ─────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Timeline */}
        <aside
          style={{
            width: 280,
            background: "var(--cds-layer-01)",
            borderRight: "1px solid var(--cds-border-subtle-00)",
            padding: "var(--spacing-04)",
            overflowY: "auto",
          }}
        >
          <p
            style={{
              fontSize: "0.625rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--cds-text-helper)",
              padding: "0 8px",
              marginBottom: 8,
            }}
          >
            Step Timeline
          </p>

          <div>
            {steps.map((step) => {
              const isActive = step.step_index === currentStepIndex;
              const isRunning = step.step_index === activeStepIndex;
              return (
                <div
                  key={step.id}
                  onClick={() => setSelectedStepIdx(step.step_index)}
                  className={`trace-step ${isActive ? "active" : ""}`}
                  style={isRunning ? { borderColor: "var(--cds-interactive)" } : {}}
                >
                  <div style={{ flexShrink: 0, marginTop: 2 }}>{getStepIcon(step.step_type)}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {step.node_key || "Node"}
                      </p>
                      <span style={{ fontSize: "0.625rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace" }}>
                        #{step.step_index}
                      </span>
                    </div>
                    <p style={{ fontSize: "0.6875rem", color: "var(--cds-text-secondary)", textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {step.step_type.replace("_", " ")}
                    </p>
                    {step.duration_ms && (
                      <p style={{ fontSize: "0.625rem", color: "var(--cds-text-helper)", fontFamily: "'IBM Plex Mono', monospace", marginTop: 2 }}>
                        {step.duration_ms}ms
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
            {steps.length === 0 && (
              <div style={{ textAlign: "center", padding: "var(--spacing-07)", fontSize: "0.75rem", color: "var(--cds-text-helper)" }}>
                Waiting for execution to begin…
              </div>
            )}
          </div>
        </aside>

        {/* Step Inspector */}
        <section
          style={{
            flex: 1,
            background: "var(--cds-background)",
            borderRight: "1px solid var(--cds-border-subtle-00)",
            padding: "var(--spacing-06)",
            overflowY: "auto",
          }}
        >
          {stepDetail ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div
                style={{
                  paddingBottom: 16,
                  borderBottom: "1px solid var(--cds-border-subtle-00)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                }}
              >
                <div>
                  <p style={{ fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--cds-text-helper)", marginBottom: 4 }}>
                    Inspector
                  </p>
                  <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cds-text-primary)" }}>
                    Block: {stepDetail.node_key || "Unknown"}
                  </h2>
                </div>
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--cds-text-secondary)",
                    fontFamily: "'IBM Plex Mono', monospace",
                    background: "var(--cds-layer-01)",
                    padding: "2px 8px",
                    border: "1px solid var(--cds-border-subtle-00)",
                    textTransform: "capitalize",
                  }}
                >
                  {stepDetail.step_type.replace("_", " ")}
                </span>
              </div>

              {stepDetail.error && (
                <div className="cds-notification error" style={{ flexDirection: "column" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
                    <AlertTriangle className="w-4 h-4" /> Fatal Step Exception
                  </div>
                  <pre style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem", marginTop: 8, overflowX: "auto", whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(stepDetail.error, null, 2)}
                  </pre>
                </div>
              )}

              {stepDetail.step_type === "llm_call" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {stepDetail.llm_request?.messages && (
                    <div>
                      <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-secondary)", marginBottom: 8 }}>System Instructions</p>
                      <pre className="code-block" style={{ whiteSpace: "pre-wrap", maxHeight: 192, overflowY: "auto" }}>
                        {stepDetail.llm_request.messages[0]?.content || "No system prompt"}
                      </pre>
                    </div>
                  )}
                  {stepDetail.llm_response && (
                    <div>
                      <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-secondary)", marginBottom: 8 }}>Assistant Output</p>
                      <pre className="code-block" style={{ whiteSpace: "pre-wrap", maxHeight: 256, overflowY: "auto" }}>
                        {String(stepDetail.llm_response)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {stepDetail.step_type === "tool_call" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div>
                    <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-secondary)", marginBottom: 8 }}>Tool Input</p>
                    <pre className="code-block" style={{ maxHeight: 192, overflowY: "auto" }}>
                      {JSON.stringify(stepDetail.tool_input, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-secondary)", marginBottom: 8 }}>Tool Output</p>
                    <pre className="code-block" style={{ maxHeight: 192, overflowY: "auto" }}>
                      {JSON.stringify(stepDetail.tool_output, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {stepDetail.step_type === "memory_read" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-secondary)" }}>Memories Retrieved</p>
                  {stepDetail.memories_retrieved?.map((m: any, idx: number) => (
                    <div
                      key={m.id || idx}
                      style={{
                        padding: "var(--spacing-04)",
                        background: "var(--cds-layer-01)",
                        border: "1px solid var(--cds-border-subtle-00)",
                        fontSize: "0.75rem",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--cds-text-secondary)", fontWeight: 600, marginBottom: 6 }}>
                        <span>Memory #{idx + 1}</span>
                        <span style={{ fontFamily: "'IBM Plex Mono', monospace", color: "var(--cds-support-info)" }}>
                          score: {m.score?.toFixed(2)}
                        </span>
                      </div>
                      <p style={{ color: "var(--cds-text-primary)", lineHeight: 1.5 }}>{m.content}</p>
                    </div>
                  ))}
                  {(!stepDetail.memories_retrieved || stepDetail.memories_retrieved.length === 0) && (
                    <p style={{ fontSize: "0.75rem", color: "var(--cds-text-helper)" }}>No records found.</p>
                  )}
                </div>
              )}

              {stepDetail.state_delta && Object.keys(stepDetail.state_delta).length > 0 && (
                <div>
                  <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--cds-text-secondary)", marginBottom: 8 }}>State Delta</p>
                  <pre className="code-block" style={{ maxHeight: 240, overflowY: "auto" }}>
                    {JSON.stringify(stepDetail.state_delta, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", color: "var(--cds-text-helper)" }}>
              <Eye className="w-8 h-8 mb-8" style={{ opacity: 0.4 }} />
              <p style={{ fontSize: "0.75rem" }}>
                Select a timeline step to inspect intermediate state.
              </p>
            </div>
          )}
        </section>

        {/* Right panel: HITL + Logs */}
        <aside
          style={{
            width: 340,
            background: "var(--cds-layer-01)",
            borderLeft: "1px solid var(--cds-border-subtle-00)",
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
          }}
        >
          {/* HITL panel */}
          {pendingHitl && (
            <div
              style={{
                padding: "var(--spacing-05)",
                borderBottom: "1px solid rgba(165,110,255,0.2)",
                background: "rgba(165,110,255,0.05)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
              className="animate-fade-in"
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    width: 8, height: 8,
                    borderRadius: "50%",
                    background: "var(--node-hitl)",
                  }}
                />
                <h3 style={{ fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--node-hitl)" }}>
                  HITL Interrupt
                </h3>
              </div>

              <p style={{ fontSize: "0.75rem", color: "var(--cds-text-secondary)", lineHeight: 1.5 }}>
                <strong>Message:</strong> {pendingHitl.message}
              </p>

              <div>
                <label className="input-label" style={{ fontSize: "0.6875rem" }}>Modify State (JSON)</label>
                <textarea
                  rows={8} className="input"
                  style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.6875rem", background: "var(--cds-background)" }}
                  value={editedStateStr} onChange={(e) => setEditedStateStr(e.target.value)}
                />
              </div>

              <div>
                <label className="input-label" style={{ fontSize: "0.6875rem" }}>Reviewer Comment</label>
                <input
                  type="text" className="input" style={{ fontSize: "0.75rem" }}
                  placeholder="Approve to run, or reason for reject…"
                  value={hitlMessage} onChange={(e) => setHitlMessage(e.target.value)}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <button onClick={() => handleHitlDecision("reject")} className="btn btn-danger" style={{ width: "100%" }}>
                  Reject
                </button>
                <button
                  onClick={() => handleHitlDecision("approve")}
                  className="btn btn-primary"
                  style={{ width: "100%", background: "var(--node-hitl)" }}
                >
                  Approve
                </button>
              </div>
            </div>
          )}

          {/* Token stream */}
          {!pendingHitl && streamingToken && (
            <div
              style={{
                padding: "var(--spacing-05)",
                borderBottom: "1px solid rgba(69,137,255,0.15)",
                background: "rgba(69,137,255,0.04)",
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              <span style={{ fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--cds-interactive)", display: "block", marginBottom: 8 }}>
                Token Stream
              </span>
              <p style={{ fontSize: "0.75rem", fontFamily: "'IBM Plex Mono', monospace", whiteSpace: "pre-wrap", lineHeight: 1.6, color: "var(--cds-text-primary)" }}>
                {streamingToken}
                <span style={{ width: 6, height: 14, background: "var(--cds-interactive)", display: "inline-block", marginLeft: 2, animation: "blink 1s infinite" }} />
              </p>
            </div>
          )}

          {/* Log output */}
          <div style={{ flex: 1, padding: "var(--spacing-05)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, color: "var(--cds-text-secondary)" }}>
              <Terminal className="w-4 h-4" />
              <span style={{ fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                WebSocket Trace Logs
              </span>
            </div>
            <div
              style={{
                flex: 1,
                background: "var(--cds-background)",
                border: "1px solid var(--cds-border-subtle-00)",
                padding: "var(--spacing-03) var(--spacing-04)",
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "0.6875rem",
                lineHeight: 1.6,
                color: "var(--cds-text-secondary)",
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              {logOutput.map((log, idx) => (
                <div key={idx} style={{ whiteSpace: "pre-wrap" }}>{log}</div>
              ))}
              {logOutput.length === 0 && (
                <div style={{ color: "var(--cds-text-helper)", textAlign: "center", padding: "var(--spacing-07) 0" }}>
                  No trace events yet.
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
}

function getStepIcon(type: string): React.ReactNode {
  switch (type) {
    case "llm_call": return <Bot className="w-4 h-4" style={{ color: "var(--node-agent)" }} />;
    case "tool_call": return <Wrench className="w-4 h-4" style={{ color: "var(--node-tool)" }} />;
    case "condition_eval": return <GitFork className="w-4 h-4" style={{ color: "var(--node-condition)" }} />;
    case "hitl_pause":
    case "hitl_resume": return <UserCheck className="w-4 h-4" style={{ color: "var(--node-hitl)" }} />;
    case "memory_read":
    case "memory_write": return <Database className="w-4 h-4" style={{ color: "var(--node-memory)" }} />;
    default: return <Cpu className="w-4 h-4" style={{ color: "var(--cds-text-secondary)" }} />;
  }
}
