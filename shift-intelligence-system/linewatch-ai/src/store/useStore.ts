import { create } from 'zustand';
import type { FloorLayout } from '../types';
import { api, WS_URL } from '../services/api';

// =============================================================================
// TYPE DEFINITIONS (EXPORTED for use in components)
// =============================================================================

export interface LogEntry {
    id: string;
    timestamp: string;
    type: string;
    source?: string;
    description?: string;
    data?: any;
}

export interface ConveyorBox {
    id: string;
    x: number;
    y: number;
    color: string;
    product_type: string;
}

export interface MachineProductionState {
    fill_level: number;
    small_boxes: number;
    product_type: string;
    product_color: string;
    is_running: boolean;
}

export interface WarehouseInventory {
    [productType: string]: number;
}

export interface Supervisor {
    id: string;
    name: string;
    x: number;
    y: number;
    status: string;
    current_action: string;
    assigned_operator_id: string | null;
}

export interface Operator {
    id: string;
    name: string;
    x: number;
    y: number;
    status: string;
    current_action: string;
    fatigue: number;  // 0-100
    on_break: boolean;
    break_requested: boolean;
}

interface State {
    // Static Data
    layout: FloorLayout | null;
    isLoading: boolean;
    error: string | null;

    // Live Data - Connection
    socket: WebSocket | null;
    isConnected: boolean;
    logs: LogEntry[];
    thoughtSignatures: Record<string, number>;
    
    // Live Data - Map Entities
    activeOperators: Record<string, any>;
    machineStates: Record<number, any>;
    cameraStates: Record<string, any>;
    
    // Live Data - Production System (NEW)
    conveyorBoxes: Record<string, ConveyorBox>;
    warehouseInventory: WarehouseInventory;
    machineProductionState: Record<number, MachineProductionState>;
    
    // Live Data - Supervisor & Fatigue (NEW)
    supervisor: Supervisor | null;
    operators: Record<string, Operator>;

    // Actions
    fetchLayout: () => Promise<void>;
    connectWebSocket: () => void;
    toggleSimulation: () => Promise<void>;
}

// =============================================================================
// STORE IMPLEMENTATION
// =============================================================================

export const useStore = create<State>((set, get) => ({
    // Initial State
    layout: null,
    isLoading: false,
    error: null,
    socket: null,
    isConnected: false,
    logs: [],
    thoughtSignatures: {},
    activeOperators: {},
    machineStates: {},
    cameraStates: {},
    
    // Production System State (NEW)
    conveyorBoxes: {},
    warehouseInventory: {},
    machineProductionState: {},
    
    // Supervisor & Fatigue State (NEW)
    supervisor: null,
    operators: {},

    // =========================================================================
    // ACTIONS
    // =========================================================================

    fetchLayout: async () => {
        set({ isLoading: true });
        try {
            const layout = await api.layout.get();
            set({ layout, isLoading: false });
        } catch (err) {
            set({ error: 'Failed to load floor layout', isLoading: false });
        }
    },

    connectWebSocket: () => {
        if (get().socket) return;

        const socket = new WebSocket(WS_URL);

        socket.onopen = () => {
            set({ isConnected: true });
            const initEntry: LogEntry = {
                id: 'sys-init',
                type: 'system',
                source: 'WebSocket',
                description: 'Connected to Agent system',
                timestamp: new Date().toISOString(),
            };
            set((state) => ({ logs: [initEntry, ...state.logs] }));
        };

        socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                
                // =============================================================
                // HIGH-FREQUENCY UPDATES (Don't log to activity feed)
                // =============================================================
                
                // Operator position updates (individual, for backwards compat)
                if (message.type === 'operator_update') {
                    set(state => ({
                        activeOperators: {
                            ...state.activeOperators,
                            [message.data.id]: message.data
                        },
                        // Also store in new operators state with fatigue data
                        operators: {
                            ...state.operators,
                            [message.data.id]: message.data
                        }
                    }));
                    return;
                }
                
                // FOG OF WAR: Visibility sync - REPLACES operators state
                // Only operators visible to cameras will appear
                if (message.type === 'visibility_sync') {
                    set({
                        operators: message.data.operators || {}
                    });
                    return;
                }

                // Camera detection updates
                if (message.type === 'camera_detection') {
                    set(state => ({
                        cameraStates: {
                            ...state.cameraStates,
                            [message.data.camera_id]: message.data
                        }
                    }));
                    return;
                }

                // Line status updates (health)
                if (message.type === 'line_status') {
                    set(state => ({
                        machineStates: {
                            ...state.machineStates,
                            [message.data.line_id]: message.data
                        }
                    }));
                    return;
                }
                
                // =============================================================
                // PRODUCTION SYSTEM UPDATES (NEW)
                // =============================================================
                
                // Machine production state (fill levels, product type)
                if (message.type === 'machine_production_state') {
                    set(state => ({
                        machineProductionState: {
                            ...state.machineProductionState,
                            [message.data.line_id]: message.data
                        }
                    }));
                    return;
                }
                
                // Large box dropped onto conveyor
                if (message.type === 'large_box_dropped') {
                    set(state => ({
                        conveyorBoxes: {
                            ...state.conveyorBoxes,
                            [message.data.id]: message.data
                        }
                    }));
                    return;
                }
                
                // Conveyor box position update
                if (message.type === 'conveyor_box_update') {
                    set(state => ({
                        conveyorBoxes: {
                            ...state.conveyorBoxes,
                            [message.data.id]: message.data
                        }
                    }));
                    return;
                }
                
                // Box arrived at warehouse
                if (message.type === 'box_arrived_warehouse') {
                    set(state => {
                        // Remove box from conveyor
                        const newConveyorBoxes = { ...state.conveyorBoxes };
                        delete newConveyorBoxes[message.data.id];
                        
                        // Update warehouse inventory
                        return {
                            conveyorBoxes: newConveyorBoxes,
                            warehouseInventory: {
                                ...state.warehouseInventory,
                                [message.data.product_type]: message.data.total
                            }
                        };
                    });
                    return;
                }
                
                // Full warehouse inventory update
                if (message.type === 'warehouse_inventory') {
                    set({ warehouseInventory: message.data });
                    return;
                }
                
                // =============================================================
                // SUPERVISOR & FATIGUE UPDATES (NEW)
                // =============================================================
                
                // Supervisor position and status update
                if (message.type === 'supervisor_update') {
                    set({ supervisor: message.data });
                    return;
                }
                
                // Camera status update (color-coded visibility)
                if (message.type === 'camera_status') {
                    set(state => ({
                        cameraStates: {
                            ...state.cameraStates,
                            [message.data.camera_id]: message.data
                        }
                    }));
                    return;
                }
                
                // Shift status update
                if (message.type === 'shift_status') {
                    // Could add shift tracking state here if needed
                    return;
                }
                
                // Shift change event
                if (message.type === 'shift_change') {
                    // Clear operators on shift change, new ones will come via operator_update
                    set({ operators: {} });
                    return;
                }
                
                // Small box created (optional - for detailed tracking)
                if (message.type === 'small_box_created') {
                    // Currently not rendered, but could be used for animations
                    return;
                }
                
                // =============================================================
                // THOUGHT SIGNATURES
                // =============================================================
                
                if (message.type === 'thought_signature') {
                    const agent = message.data?.agent;
                    const count = message.data?.total_signatures || 0;
                    if (agent) {
                        set((state) => ({
                            thoughtSignatures: {
                                ...state.thoughtSignatures,
                                [agent]: count
                            }
                        }));
                    }
                    return;
                }
                
                // =============================================================
                // SYSTEM STATUS (Don't clutter activity log)
                // =============================================================
                
                if (message.type === 'system_status') {
                    return;
                }
                
                // =============================================================
                // LOGGABLE EVENTS (Show in Activity Log)
                // =============================================================
                
                // Helper to format actions or thoughts
                let description = message.data?.description;
                
                if (!description) {
                    if (message.data?.thought) {
                        description = `💭 ${message.data.thought}`;
                    } else if (message.data?.actions && Array.isArray(message.data.actions)) {
                        description = `Exec: ${message.data.actions.join(', ')}`;
                    } else if (message.data?.reasoning) {
                         description = message.data.reasoning;
                    } else {
                        description = JSON.stringify(message.data);
                    }
                }

                const logEntry: LogEntry = {
                    id: `log-${Date.now()}-${Math.random()}`,
                    type: message.type || 'unknown',
                    source: message.data?.source || message.data?.agent || 'System',
                    description: description,
                    timestamp: message.data?.timestamp || new Date().toISOString(),
                    data: message.data,
                };

                set((state) => ({
                    logs: [logEntry, ...state.logs].slice(0, 100),
                }));
            } catch (err) {
                console.error('Failed to parse WebSocket message:', err);
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            set({ isConnected: false });
        };

        socket.onclose = () => {
            set({ isConnected: false, socket: null });
        };

        set({ socket });
        
        // Expose WebSocket globally for ThoughtBubble component
        (window as any).__agentWebSocket = socket;
    },
    
    toggleSimulation: async () => {
        try {
            const status = await api.simulation.getStatus();
            
            if (status.running) {
                await api.simulation.stop();
                // Clear production state on stop
                set({
                    conveyorBoxes: {},
                    machineProductionState: {},
                });
            } else {
                await api.simulation.start();
                // Clear state on start (fresh simulation)
                set({
                    conveyorBoxes: {},
                    warehouseInventory: {},
                    machineProductionState: {},
                });
            }
        } catch(e) { 
            console.error('Failed to toggle simulation:', e);
        }
    }
}));
