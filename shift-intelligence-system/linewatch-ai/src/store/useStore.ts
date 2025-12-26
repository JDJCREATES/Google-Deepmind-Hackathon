import { create } from 'zustand';
import { api } from '../services/api';

// =============================================================================
// TYPES
// =============================================================================

export interface LayoutData {
    dimensions: { width: number; height: number };
    zones: ZoneData[];
    lines: MachineData[];
    cameras: CameraData[];
    conveyors: ConveyorData[];
    operators: OperatorData[];
}

export interface ZoneData {
    id: string;
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
    color: string;
}

export interface MachineData {
    id: number;
    label: string;
    x: number;
    y: number;
    machine_w: number;
    machine_h: number;
    equip_w: number;
    equip_h: number;
    status: string;
    health: number;
    last_issue?: string;
}

export interface CameraData {
    id: string;
    line_id: number;
    x: number;
    y: number;
    rotation: number;
    fov: number;
    range: number;
    label: string;
    status: string;
}

export interface OperatorData {
    id: string;
    name: string;
    x: number;
    y: number;
    status: string;
    assigned_lines: number[];
}

export interface ConveyorData {
    id: string;
    x: number;
    y: number;
    width: number;
    height: number;
    direction: string;
    status: string;
}

// NEW: Real-time production entities
export interface ConveyorBox {
    id: string;
    x: number;
    y: number;
    color: string;
    type: string;
}

export interface WarehouseInventory {
    [productType: string]: number;
}

export interface MachineProductionState {
    fill_level: number;
    small_boxes: number;
    product_type: string;
    product_color: string;
    is_running: boolean;
}

// Supervisor Entity (NEW)
export interface Supervisor {
    id: string;
    name: string;
    x: number;
    y: number;
    status: string; // 'idle', 'moving_to_operator', 'relieving', 'returning'
    current_action: string;
}

export interface LogEntry {
    id: string;
    type: string;
    source: string;
    description: string;
    timestamp: string;
    data?: any;
}

interface State {
    layout: LayoutData | null;
    isLoading: boolean;
    error: string | null;
    socket: WebSocket | null;
    isConnected: boolean;
    logs: LogEntry[];
    
    // Thought tracking (deduplication)
    thoughtSignatures: Record<string, number>; // hash -> timestamp

    // Real-time State
    activeOperators: Record<string, OperatorData>;
    machineStates: Record<number, MachineData>;
    cameraStates: Record<string, CameraData>;
    
    // NEW: Production System State
    conveyorBoxes: Record<string, ConveyorBox>;
    warehouseInventory: WarehouseInventory;
    machineProductionState: Record<number, MachineProductionState>;
    
    // NEW: Supervisor & Fatigue
    supervisor: Supervisor | null;
    operators: Record<string, OperatorData>; // Centralized operators state (with fatigue)
    
    // NEW: Maintenance Crew
    maintenanceCrew: Supervisor | null; // Re-use Supervisor type for now as structure is similar

    // Actions
    fetchLayout: () => Promise<void>;
    connectWebSocket: () => void;
    toggleSimulation: () => Promise<void>;
}

export const useStore = create<State>((set, get) => ({
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
    
    conveyorBoxes: {},
    warehouseInventory: {},
    machineProductionState: {},
    
    supervisor: null,
    operators: {},
    maintenanceCrew: null,

    fetchLayout: async () => {
        set({ isLoading: true });
        try {
            const data = await api.layout.get();
            set({ layout: data, isLoading: false });
        } catch (err) {
            set({ error: 'Failed to fetch layout', isLoading: false });
        }
    },

    connectWebSocket: () => {
        if (get().socket?.readyState === WebSocket.OPEN) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // FIXED: Endpoint must match backend definition @app.websocket("/ws/stream")
        const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/stream`;
        
        console.log('Connecting to WebSocket:', wsUrl);
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('WebSocket Connected');
            set({ isConnected: true, error: null });
        };

        socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                
                // Active Operators (Movement)
                if (message.type === 'operator_update') {
                    // Update the centralized operators state
                    // This handles creating new operators if they don't exist
                    set(state => ({
                        operators: {
                            ...state.operators,
                            [message.data.id]: message.data
                        },
                        // Keep legacy activeOperators for backward compatibility if needed
                         activeOperators: {
                            ...state.activeOperators,
                            [message.data.id]: message.data,
                        }
                    }));
                    return;
                }

                // Operator Fatigue / Status Updates
                if (message.type === 'operator_fatigue_update') {
                     set(state => ({
                        operators: {
                            ...state.operators,
                            [message.data.id]: {
                                ...(state.operators[message.data.id] || {}), // Merge with existing
                                ...message.data // Apply updates (fatigue, status, on_break)
                            }
                        }
                    }));
                    return;
                }

                // Supervisor updates
                if (message.type === 'supervisor_update') {
                    set({ supervisor: message.data });
                    return;
                }
                
                // Maintenance Crew updates
                if (message.type === 'maintenance_crew_update') {
                    set({ maintenanceCrew: message.data });
                    return;
                }

                // Shift status updates
                if (message.type === 'shift_status') {
                     // Log shift status changes
                     // We could store this in state if needed
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
                            [message.data.machine_id]: message.data
                        }
                    }));
                    return;
                }

                // Global inventory update
                if (message.type === 'inventory_update') {
                     set({ warehouseInventory: message.data });
                     return;
                }
                
                // Conveyor box movement (high frequency)
                if (message.type === 'conveyor_update') {
                    // message.data is the Full boxes dict {box_id: Box}
                    set({ conveyorBoxes: message.data });
                    return;
                }

                // =============================================================

                if (message.type === 'camera_update') {
                    set((state) => ({
                        cameraStates: {
                            ...state.cameraStates,
                            [message.data.id]: message.data
                        }
                    }));
                    return;
                }

                // LOGGING (Filtered)
                // Avoid logging high-frequency updates
                if (['operator_update', 'conveyor_update', 'machine_production_state', 'camera_update', 'supervisor_update', 'operator_fatigue_update', 'shift_status', 'inventory_update', 'line_status', 'maintenance_crew_update'].includes(message.type)) {
                    return;
                }
                
                // Deduplicate Agent Thoughts
                let description = message.data?.thought || JSON.stringify(message.data);
                
                if (message.type === 'agent_thought') {
                    const now = Date.now();
                    // Create a simple hash of the thought content
                    const thoughtHash = description.split('').reduce((a: number, b: string) => { a = ((a << 5) - a) + b.charCodeAt(0); return a & a }, 0);
                    const lastSeen = get().thoughtSignatures[thoughtHash];
                    
                    // If we saw this exact thought in the last 2 seconds, skip it
                    if (lastSeen && (now - lastSeen < 2000)) {
                        return;
                    }
                    
                    // Update signature cache
                    set(state => ({
                        thoughtSignatures: {
                            ...state.thoughtSignatures,
                            [thoughtHash]: now
                        }
                    }));
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
            setTimeout(() => get().connectWebSocket(), 3000);
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
                set({
                    conveyorBoxes: {},
                    machineProductionState: {},
                });
            } else {
                await api.simulation.start();
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
