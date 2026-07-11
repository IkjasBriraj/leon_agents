/**
 * Custom React Flow Visual Node Types
 *
 * Implements themed styles for each workflow component block following the
 * IBM Carbon Design System (g100) specifications.
 */

import React from "react";
import { Handle, Position } from "@xyflow/react";
import { Bot, Wrench, GitFork, UserCheck, Database, Code, Play, CheckCircle } from "lucide-react";

interface NodeProps {
  data: {
    label: string;
    config: any;
  };
  selected?: boolean;
}

// ─── Start / End Nodes ────────────────────────────────────────────────────────

export function StartNode({ data, selected }: NodeProps) {
  return (
    <div className={`px-4 py-2 rounded-full border bg-[#42be65]/10 border-[#42be65]/30 text-[#42be65] font-semibold flex items-center gap-1.5 text-xs shadow-sm transition-all duration-150 ${selected ? "ring-2 ring-[#42be65]/50 scale-105" : ""}`}>
      <Play className="w-3.5 h-3.5 fill-current" />
      <span>{data.label || "Start"}</span>
      <Handle type="source" position={Position.Right} className="!bg-[#42be65]" />
    </div>
  );
}

export function EndNode({ data, selected }: NodeProps) {
  return (
    <div className={`px-4 py-2 rounded-full border bg-[#da1e28]/10 border-[#da1e28]/30 text-[#ff8389] font-semibold flex items-center gap-1.5 text-xs shadow-sm transition-all duration-150 ${selected ? "ring-2 ring-[#da1e28]/50 scale-105" : ""}`}>
      <CheckCircle className="w-3.5 h-3.5" />
      <span>{data.label || "End"}</span>
      <Handle type="target" position={Position.Left} className="!bg-[#ff8389]" />
    </div>
  );
}

// ─── Agent Node ───────────────────────────────────────────────────────────────

export function AgentNode({ data, selected }: NodeProps) {
  return (
    <div className={`glass-card p-3 w-[200px] border-l-4 border-l-[#4589ff] relative transition-all duration-150 ${selected ? "ring-2 ring-[#4589ff]/50 scale-105 border-[#78a9ff]" : ""}`}>
      <Handle type="target" position={Position.Left} className="!bg-[#4589ff]" />

      <header className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-sm bg-[#4589ff]/10 border border-[#4589ff]/20 text-[#78a9ff] flex items-center justify-center">
          <Bot className="w-3.5 h-3.5" />
        </div>
        <span className="font-semibold text-xs text-[#f4f4f4] leading-tight">{data.label}</span>
      </header>

      <div className="text-[10px] text-[#c6c6c6] font-mono bg-[#1a1a1a] px-1.5 py-0.5 rounded border border-[#393939] inline-block">
        {data.config?.model_name || "llama3.2"}
      </div>

      <Handle type="source" position={Position.Right} className="!bg-[#4589ff]" />
    </div>
  );
}

// ─── Tool Node ────────────────────────────────────────────────────────────────

export function ToolNode({ data, selected }: NodeProps) {
  return (
    <div className={`glass-card p-3 w-[200px] border-l-4 border-l-[#ff832b] relative transition-all duration-150 ${selected ? "ring-2 ring-[#ff832b]/50 scale-105 border-[#ffb784]" : ""}`}>
      <Handle type="target" position={Position.Left} className="!bg-[#ffb784]" />

      <header className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-sm bg-[#ff832b]/10 border border-[#ff832b]/20 text-[#ffb784] flex items-center justify-center">
          <Wrench className="w-3.5 h-3.5" />
        </div>
        <span className="font-semibold text-xs text-[#f4f4f4] leading-tight">{data.label}</span>
      </header>

      <div className="text-[10px] text-[#c6c6c6] font-mono">
        dispatcher → <span className="text-[#ffb784]">{data.config?.tool_name || "web_search"}</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-[#ffb784]" />
    </div>
  );
}

// ─── Condition Node ───────────────────────────────────────────────────────────

export function ConditionNode({ data, selected }: NodeProps) {
  const expr = data.config?.expression || {};
  return (
    <div className={`glass-card p-3 w-[200px] border-l-4 border-l-[#f1c21b] relative transition-all duration-150 ${selected ? "ring-2 ring-[#f1c21b]/50 scale-105 border-[#f1c21b]" : ""}`}>
      <Handle type="target" position={Position.Left} className="!bg-[#f1c21b]" />

      <header className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-sm bg-[#f1c21b]/10 border border-[#f1c21b]/20 text-[#f1c21b] flex items-center justify-center">
          <GitFork className="w-3.5 h-3.5" />
        </div>
        <span className="font-semibold text-xs text-[#f4f4f4] leading-tight">{data.label}</span>
      </header>

      <div className="text-[10px] text-[#c6c6c6] font-mono leading-none truncate" title={`${expr.field} ${expr.op} ${expr.value}`}>
        {expr.field?.replace("context.", "")} {expr.op} {expr.value}
      </div>

      <Handle type="source" position={Position.Right} className="!bg-[#f1c21b]" />
    </div>
  );
}

// ─── HITL Gate Node ───────────────────────────────────────────────────────────

export function HitlGateNode({ data, selected }: NodeProps) {
  return (
    <div className={`glass-card p-3 w-[200px] border-l-4 border-l-[#a56eff] relative transition-all duration-150 ${selected ? "ring-2 ring-[#a56eff]/50 scale-105 border-[#d4bbff]" : ""}`}>
      <Handle type="target" position={Position.Left} className="!bg-[#d4bbff]" />

      <header className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-sm bg-[#a56eff]/10 border border-[#a56eff]/20 text-[#d4bbff] flex items-center justify-center">
          <UserCheck className="w-3.5 h-3.5" />
        </div>
        <span className="font-semibold text-xs text-[#f4f4f4] leading-tight">{data.label}</span>
      </header>

      <p className="text-[9px] text-[#c6c6c6] leading-tight truncate">
        {data.config?.message || "Wait for human review..."}
      </p>

      <Handle type="source" position={Position.Right} className="!bg-[#d4bbff]" />
    </div>
  );
}

// ─── Memory Node ──────────────────────────────────────────────────────────────

export function MemoryNode({ data, selected }: NodeProps) {
  return (
    <div className={`glass-card p-3 w-[200px] border-l-4 border-l-[#08bdba] relative transition-all duration-150 ${selected ? "ring-2 ring-[#08bdba]/50 scale-105 border-[#3ddbd9]" : ""}`}>
      <Handle type="target" position={Position.Left} className="!bg-[#3ddbd9]" />

      <header className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-sm bg-[#08bdba]/10 border border-[#08bdba]/20 text-[#3ddbd9] flex items-center justify-center">
          <Database className="w-3.5 h-3.5" />
        </div>
        <span className="font-semibold text-xs text-[#f4f4f4] leading-tight">{data.label}</span>
      </header>

      <div className="text-[10px] text-[#c6c6c6] font-mono leading-none capitalize">
        layer → <span className="text-[#3ddbd9]">{data.config?.memory_type || "episodic"}</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-[#3ddbd9]" />
    </div>
  );
}

// ─── Code Sandbox Node ────────────────────────────────────────────────────────

export function CodeNode({ data, selected }: NodeProps) {
  return (
    <div className={`glass-card p-3 w-[200px] border-l-4 border-l-[#525252] relative transition-all duration-150 ${selected ? "ring-2 ring-[#525252]/50 scale-105 border-[#c6c6c6]" : ""}`}>
      <Handle type="target" position={Position.Left} className="!bg-[#c6c6c6]" />

      <header className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-sm bg-[#525252]/20 border border-[#525252]/40 text-[#c6c6c6] flex items-center justify-center">
          <Code className="w-3.5 h-3.5" />
        </div>
        <span className="font-semibold text-xs text-[#f4f4f4] leading-tight">{data.label}</span>
      </header>

      <div className="text-[10px] text-[#c6c6c6] font-mono capitalize">
        isolated → <span className="text-[#f4f4f4] font-semibold">{data.config?.language || "python"}</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-[#c6c6c6]" />
    </div>
  );
}

// Export custom mappings object
export const nodeTypesMap = {
  start: StartNode,
  end: EndNode,
  agent: AgentNode,
  tool: ToolNode,
  condition: ConditionNode,
  hitl_gate: HitlGateNode,
  memory_read: MemoryNode,
  memory_write: MemoryNode,
  code: CodeNode,
};
