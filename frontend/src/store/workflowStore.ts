/**
 * Workflow Store — Zustand
 *
 * Manages the React Flow canvas state (nodes, edges) and coordinates
 * database persistence (saving, loading, creating, updating) and
 * structural graph validation.
 */

import { create } from "zustand";
import {
  type Edge,
  type Node,
  type OnConnect,
  type OnEdgesChange,
  type OnNodesChange,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react";
import { api, type Workflow, type WorkflowNode, type WorkflowEdge } from "@/lib/api";

interface WorkflowState {
  // Graph Canvas State
  workflowId: string | null;
  workflowName: string;
  workflowDescription: string;
  nodes: Node[];
  edges: Edge[];
  viewport: { x: number; y: number; zoom: number };
  status: string;
  version: number;

  // UI state
  isLoading: boolean;
  isSaving: boolean;
  selectedNodeId: string | null;

  // Graph Validation Results
  validation: {
    isValid: boolean;
    errors: string[];
    warnings: string[];
  } | null;

  // Canvas Handlers
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;

  // Node operations
  addNode: (type: string, position: { x: number; y: number }) => void;
  deleteNode: (id: string) => void;
  updateNodeConfig: (id: string, config: any) => void;
  updateNodeLabel: (id: string, label: string) => void;
  selectNode: (id: string | null) => void;

  // DB Sync Actions
  loadWorkflow: (id: string) => Promise<void>;
  saveWorkflow: () => Promise<void>;
  createWorkflow: (name: string, description: string) => Promise<string>;
  validateGraph: () => Promise<void>;
  reset: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflowId: null,
  workflowName: "Untitled Workflow",
  workflowDescription: "",
  nodes: [],
  edges: [],
  viewport: { x: 0, y: 0, zoom: 1 },
  status: "draft",
  version: 1,

  isLoading: false,
  isSaving: false,
  selectedNodeId: null,
  validation: null,

  // ─── React Flow Canvas Handlers ──────────────────────────────────────────────

  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    }));
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
    }));
  },

  onConnect: (connection) => {
    set((state) => ({
      edges: addEdge(
        {
          ...connection,
          id: `edge-${Date.now()}`,
          type: "default",
          data: { edgeType: "default" },
        },
        state.edges
      ),
    }));
  },

  // ─── Node / Edge Operations ──────────────────────────────────────────────────

  addNode: (type, position) => {
    const id = `${type}-${Date.now()}`;
    const newNode: Node = {
      id,
      type,
      position,
      data: {
        label: `${type.charAt(0).toUpperCase() + type.slice(1)} Node`,
        config: getDefaultConfig(type),
      },
    };

    set((state) => ({
      nodes: [...state.nodes, newNode],
    }));
  },

  deleteNode: (id) => {
    set((state) => ({
      nodes: state.nodes.filter((node) => node.id !== id),
      edges: state.edges.filter((edge) => edge.source !== id && edge.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
    }));
  },

  updateNodeConfig: (id, config) => {
    set((state) => ({
      nodes: state.nodes.map((node) => {
        if (node.id === id) {
          return {
            ...node,
            data: {
              ...node.data,
              config: { ...(node.data.config as any || {}), ...config },
            },
          };
        }
        return node;
      }),
    }));
  },

  updateNodeLabel: (id, label) => {
    set((state) => ({
      nodes: state.nodes.map((node) => {
        if (node.id === id) {
          return { ...node, data: { ...node.data, label } };
        }
        return node;
      }),
    }));
  },

  selectNode: (id) => {
    set({ selectedNodeId: id });
  },

  // ─── Database Sync Actions ──────────────────────────────────────────────────

  loadWorkflow: async (id) => {
    set({ isLoading: true, selectedNodeId: null, validation: null });
    try {
      const data = await api.get<Workflow>(`/workflows/${id}`);

      // Map backend WorkflowNodes to React Flow Node layout
      const flowNodes: Node[] = data.nodes.map((n) => ({
        id: n.node_key,
        type: n.node_type,
        position: { x: n.position_x, y: n.position_y },
        data: {
          label: n.label || `${n.node_type} node`,
          config: n.config,
        },
      }));

      // Map backend WorkflowEdges to React Flow Edge layout
      const flowEdges: Edge[] = data.edges.map((e) => {
        // Resolve source/target keys from IDs
        const sourceNode = data.nodes.find((n) => n.id === e.source_node_id);
        const targetNode = data.nodes.find((n) => n.id === e.target_node_id);
        return {
          id: e.id,
          source: sourceNode?.node_key || "",
          target: targetNode?.node_key || "",
          label: e.label || undefined,
          type: e.edge_type,
          animated: e.edge_type === "loop_back",
          data: {
            condition: e.condition,
            priority: e.priority,
            edgeType: e.edge_type,
          },
        };
      });

      set({
        workflowId: data.id,
        workflowName: data.name,
        workflowDescription: data.description || "",
        nodes: flowNodes,
        edges: flowEdges,
        viewport: data.viewport || { x: 0, y: 0, zoom: 1 },
        status: data.status,
        version: data.version,
      });

      // Automatically run validation on load
      await get().validateGraph();
    } catch (err) {
      console.error("Failed to load workflow:", err);
      throw err;
    } finally {
      set({ isLoading: false });
    }
  },

  saveWorkflow: async () => {
    const { workflowId, workflowName, workflowDescription, nodes, edges, viewport } = get();
    if (!workflowId) return;

    set({ isSaving: true });
    try {
      // Package up backend format nodes
      const payloadNodes = nodes.map((node) => ({
        node_key: node.id,
        node_type: node.type || "agent",
        label: String(node.data.label || ""),
        config: node.data.config || {},
        position_x: node.position.x,
        position_y: node.position.y,
      }));

      // Package up backend format edges
      const payloadEdges = edges.map((edge) => ({
        source_node_id: edge.source, // temporarily set to keys, API resolves to DB IDs
        target_node_id: edge.target, // temporarily set to keys, API resolves to DB IDs
        edge_type: String(edge.type || "default"),
        condition: edge.data?.condition || null,
        label: edge.label ? String(edge.label) : null,
        priority: Number(edge.data?.priority || 0),
        style: edge.style || {},
      }));

      await api.patch(`/workflows/${workflowId}`, {
        name: workflowName,
        description: workflowDescription,
        nodes: payloadNodes,
        edges: payloadEdges,
        viewport,
      });

      await get().validateGraph();
    } catch (err) {
      console.error("Failed to save workflow:", err);
      throw err;
    } finally {
      set({ isSaving: false });
    }
  },

  createWorkflow: async (name, description) => {
    try {
      const data = await api.post<{ id: string }>("/workflows", {
        name,
        description,
        nodes: [
          { node_key: "start", node_type: "start", label: "Start", position_x: 100, position_y: 200 },
          { node_key: "end", node_type: "end", label: "End", position_x: 600, position_y: 200 },
        ],
        edges: [],
      });
      return data.id;
    } catch (err) {
      console.error("Failed to create workflow:", err);
      throw err;
    }
  },

  validateGraph: async () => {
    const { workflowId } = get();
    if (!workflowId) return;

    try {
      const data = await api.get<any>(`/workflows/${workflowId}/validate`);
      set({
        validation: {
          isValid: data.valid,
          errors: data.errors,
          warnings: data.warnings,
        },
      });
    } catch (err) {
      console.error("Graph validation failed:", err);
    }
  },

  reset: () => {
    set({
      workflowId: null,
      workflowName: "Untitled Workflow",
      workflowDescription: "",
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      status: "draft",
      version: 1,
      selectedNodeId: null,
      validation: null,
    });
  },
}));

/**
 * Returns default configurations for each node type.
 */
function getDefaultConfig(type: string): any {
  switch (type) {
    case "agent":
      return {
        agent_id: "",
        system_prompt_override: "",
        temperature: 0.7,
      };
    case "tool":
      return {
        tool_name: "web_search",
        fixed_args: {},
      };
    case "condition":
      return {
        expression: {
          field: "context.result",
          op: "eq",
          value: "",
        },
      };
    case "hitl_gate":
      return {
        message: "Human verification requested.",
        approval_roles: ["member"],
        timeout_seconds: 3600,
      };
    case "memory_read":
      return {
        query: "$message",
        k: 5,
        context_key: "retrieved_knowledge",
      };
    case "memory_write":
      return {
        content_path: "context.result",
        memory_type: "episodic",
        importance: 0.6,
      };
    case "code":
      return {
        source_code: "# Run custom logic here\nprint('Hello from AgentCraft')",
        language: "python",
      };
    default:
      return {};
  }
}
