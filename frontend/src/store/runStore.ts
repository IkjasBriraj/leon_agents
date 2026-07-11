/**
 * Execution Run Store — Zustand
 *
 * Coordinates running agentic workflows, connecting to the real-time
 * WebSocket debugger/trace engine, streaming output tokens, handling
 * step-through execution, and submitting human decisions (HITL).
 */

import { create } from "zustand";
import Cookies from "js-cookie";
import { api, WS_BASE_URL, type Run, type RunStep } from "@/lib/api";

interface RunState {
  currentRun: Run | null;
  steps: RunStep[];
  activeStepIndex: number | null;
  activeNodeKey: string | null;

  // Real-time streaming and debug logs
  logOutput: string[];
  streamingToken: string;
  isExecuting: boolean;

  // HITL Interrupt Panel
  pendingHitl: {
    nodeKey: string;
    stepIndex: number;
    message: string;
    approvalRoles: string[];
    stateSnapshot: any;
  } | null;

  // Actions
  triggerRun: (workflowId: string, inputData: any) => Promise<string>;
  loadRun: (runId: string) => Promise<void>;
  connectWebSocket: (runId: string) => void;
  disconnectWebSocket: () => void;
  resumeRun: (decision: "approve" | "reject", editedState?: any, message?: string) => Promise<void>;
  cancelRun: () => Promise<void>;
  selectStep: (index: number | null) => void;
  reset: () => void;
}

let ws: WebSocket | null = null;

export const useRunStore = create<RunState>((set, get) => ({
  currentRun: null,
  steps: [],
  activeStepIndex: null,
  activeNodeKey: null,

  logOutput: [],
  streamingToken: "",
  isExecuting: false,

  pendingHitl: null,

  // ─── Actions ────────────────────────────────────────────────────────────────

  triggerRun: async (workflowId, inputData) => {
    set({ isExecuting: true, logOutput: ["Enqueuing workflow run..."], steps: [], activeStepIndex: null, pendingHitl: null });
    try {
      const data = await api.post<{ id: string }>("/runs", {
        workflow_id: workflowId,
        input_data: inputData,
      });

      // Fetch initial run record
      await get().loadRun(data.id);

      // Connect WebSocket to stream execution traces in real-time
      get().connectWebSocket(data.id);

      return data.id;
    } catch (err) {
      set({ isExecuting: false, logOutput: [`Failed to trigger execution: ${err}`] });
      throw err;
    }
  },

  loadRun: async (runId) => {
    try {
      const run = await api.get<Run>(`/runs/${runId}`);
      set({
        currentRun: run,
        steps: run.steps || [],
        isExecuting: ["pending", "running", "paused_hitl"].includes(run.status),
      });

      // If loaded run is paused for human approval, check if we need to show HITL UI
      if (run.status === "paused_hitl" && run.checkpoint_state) {
        // Find node key from the active step or checkpoint state
        const lastStep = run.steps?.[run.steps.length - 1];
        set({
          pendingHitl: {
            nodeKey: lastStep?.node_key || "hitl_gate",
            stepIndex: lastStep?.step_index || 0,
            message: "Execution paused. Review state parameters and approve to continue.",
            approvalRoles: ["member"],
            stateSnapshot: run.checkpoint_state,
          },
        });
      }
    } catch (err) {
      console.error("Failed to load run details:", err);
    }
  },

  connectWebSocket: (runId) => {
    get().disconnectWebSocket();

    const token = Cookies.get("agentcraft_token");
    const wsUrl = `${WS_BASE_URL}/ws/runs/${runId}${token ? `?token=${token}` : ""}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      set((state) => ({
        logOutput: [...state.logOutput, `[Trace Channel] WebSocket connection established.`],
      }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      switch (msg.type) {
        case "step_start":
          set((state) => ({
            activeNodeKey: msg.node_key,
            activeStepIndex: msg.step_index,
            streamingToken: "",
            logOutput: [
              ...state.logOutput,
              `[Step #${msg.step_index}] Entering node ${msg.node_key} (${msg.node_type})`,
            ],
          }));
          break;

        case "step_end":
          // Refresh run record to pull updated step history
          get().loadRun(runId);
          set((state) => ({
            streamingToken: "",
            logOutput: [
              ...state.logOutput,
              `[Step #${msg.step_index}] Completed in ${msg.duration_ms}ms`,
            ],
          }));
          break;

        case "llm_stream":
          set((state) => ({
            streamingToken: state.streamingToken + msg.chunk,
          }));
          break;

        case "tool_called":
          set((state) => ({
            logOutput: [
              ...state.logOutput,
              `[Tool call] Dispatched '${msg.tool_name}' with parameters: ${JSON.stringify(msg.tool_input)}`,
            ],
          }));
          break;

        case "hitl_required":
          set((state) => ({
            isExecuting: false,
            pendingHitl: {
              nodeKey: msg.node_key,
              stepIndex: msg.step_index,
              message: msg.message,
              approvalRoles: msg.approval_roles,
              stateSnapshot: msg.state_snapshot,
            },
            logOutput: [
              ...state.logOutput,
              `[HITL Interrupt] Execution paused at gate node: ${msg.node_key}`,
            ],
          }));
          break;

        case "memory_retrieved":
          set((state) => ({
            logOutput: [
              ...state.logOutput,
              `[Memory Retrieve] Loaded ${msg.memories.length} relevant context documents`,
            ],
          }));
          break;

        case "run_complete":
          get().disconnectWebSocket();
          get().loadRun(runId);
          set((state) => ({
            isExecuting: false,
            activeNodeKey: null,
            logOutput: [
              ...state.logOutput,
              `[Success] Workflow execution completed successfully.`,
            ],
          }));
          break;

        case "run_error":
          get().disconnectWebSocket();
          get().loadRun(runId);
          set((state) => ({
            isExecuting: false,
            activeNodeKey: null,
            logOutput: [
              ...state.logOutput,
              `[Fatal error] Execution halted: ${msg.error?.message || "Unknown error"}`,
            ],
          }));
          break;
      }
    };

    ws.onclose = () => {
      set((state) => ({
        logOutput: [...state.logOutput, `[Trace Channel] WebSocket connection closed.`],
      }));
    };

    ws.onerror = (err) => {
      console.error("WS error:", err);
    };
  },

  disconnectWebSocket: () => {
    if (ws) {
      ws.close();
      ws = null;
    }
  },

  resumeRun: async (decision, editedState, message) => {
    const { currentRun, pendingHitl } = get();
    if (!currentRun || !pendingHitl) return;

    set({ pendingHitl: null, isExecuting: true });
    try {
      await api.post(`/runs/${currentRun.id}/resume`, {
        decision,
        edited_state: editedState,
        message,
      });

      set((state) => ({
        logOutput: [
          ...state.logOutput,
          `[HITL Response] Submitted '${decision}' decision. Re-starting state machine...`,
        ],
      }));
    } catch (err) {
      console.error("Failed to resume execution:", err);
      set({ isExecuting: false });
    }
  },

  cancelRun: async () => {
    const { currentRun } = get();
    if (!currentRun) return;

    try {
      await api.post(`/runs/${currentRun.id}/cancel`);
      get().disconnectWebSocket();
      await get().loadRun(currentRun.id);
    } catch (err) {
      console.error("Failed to cancel run:", err);
    }
  },

  selectStep: (index) => {
    set({ activeStepIndex: index });
  },

  reset: () => {
    get().disconnectWebSocket();
    set({
      currentRun: null,
      steps: [],
      activeStepIndex: null,
      activeNodeKey: null,
      logOutput: [],
      streamingToken: "",
      isExecuting: false,
      pendingHitl: null,
    });
  },
}));
