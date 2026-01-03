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
    color?: string;
}

export interface OperatorData {
    id: string;
    name: string;
    x?: number;  // Optional for Fog of War - only set when visible
    y?: number;  // Optional for Fog of War - only set when visible
    status: string;
    assigned_lines: number[];
    visible_to_cameras?: boolean; // Fog of War visibility flag
    fatigue?: number;
    on_break?: boolean;
    break_requested?: boolean;
    current_action?: string;
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

export interface SupervisorState {
    id: string;
    x: number;
    y: number;
    status: string;
    current_action: string;
    assigned_operator_id?: string;
    path_index: number;
    target_x?: number;
    target_y?: number;
}

// Maintenance Crew Entity
export interface MaintenanceCrewState {
    x: number;
    y: number;
    status: string;
    current_action: string;
    assigned_machine_id?: string;
}

// NEW: Financial State
export interface FinancialState {
    balance: number;
    total_revenue: number;
    total_expenses: number;
    hourly_wage_cost: number;
    last_updated: string;
}

// NEW: Performance Metrics
export interface PerformanceMetrics {
    oee: number;
    availability: number;
    performance: number;
    safety_score: number;
    uptime_hours: number;
}

// NEW: Full Simulation State
export interface SimulationState {
    timestamp: string;
    financials: FinancialState;
    kpi: PerformanceMetrics;
    inventory: WarehouseInventory;
    line_health: {[key: string]: number};
    shift_elapsed_hours: number;
}


export interface StoreState {
    // NEW: Financials & Metrics
    financials: FinancialState;
    kpi: PerformanceMetrics;
    
    // Layout
    dimensions: { width: number; height: number };
    zones: ZoneData[];
    
    // Entities
    machines: MachineData[];
    cameras: CameraData[];
    conveyors: ConveyorData[];
    conveyorBoxes: ConveyorBox[];
    operators: OperatorData[];
    supervisor: SupervisorState | null;
    maintenanceCrew: MaintenanceCrewState | null;
    
    // NEW: Financials
    financials: FinancialState;
    
    // State
    warehouseInventory: WarehouseInventory;
    machineProduction: {[key: number]: MachineProductionState};
    
    // Actions
    setDimensions: (width: number, height: number) => void;
    setZones: (zones: ZoneData[]) => void;
    setMachines: (machines: MachineData[]) => void;
    updateMachine: (id: number, data: Partial<MachineData>) => void;
    setCameras: (cameras: CameraData[]) => void;
    setConveyors: (conveyors: ConveyorData[]) => void;
    setOperators: (operators: OperatorData[]) => void;
    updateOperator: (id: string, data: Partial<OperatorData>) => void;
    setSupervisor: (supervisor: SupervisorState) => void;
    setMaintenanceCrew: (crew: MaintenanceCrewState) => void;
    
    // Logs (Persisted)
    logs: LogEntry[];
    addLog: (log: LogEntry) => void;
    clearLogs: () => void;
    setLogs: (logs: LogEntry[]) => void;
    
    // Selection
    selectedEntityId: string | null;
    selectedEntityType: 'operator' | 'machine' | 'camera' | 'supervisor' | null;
    setSelectedEntity: (id: string | null, type: 'operator' | 'machine' | 'camera' | 'supervisor' | null) => void;
    
    // Simulation Control
    simStatus: { running: boolean; uptime: number };
    setSimStatus: (status: { running: boolean; uptime: number }) => void;
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

export const useStore = create<State>()(
    (set, get) => ({
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

    // NEW: Financials Initial State
    financials: {
        balance: 10000.0,
        total_revenue: 0.0,
        total_expenses: 0.0,
        hourly_wage_cost: 0.0,
        last_updated: new Date().toISOString()
    },
    
    kpi: {
        oee: 1.0,
        availability: 1.0,
        performance: 1.0,
        safety_score: 100.0,
        uptime_hours: 0.0
    },

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
                
                // Handle batched updates from backend (reduces WebSocket overhead)
                if (message.type === 'batch_update') {
                    const events = message.data.events || [];
                    events.forEach((evt: any) => {
                        // Recursively handle each event as if it came separately
                        socket.onmessage?.({ data: JSON.stringify(evt) } as MessageEvent);
                    });
                    return;
                }
                
                // Handle log history from backend on reconnect
                if (message.type === 'log_history') {
                    const historicalLogs = message.data.logs || [];
                    set(state => {
                        // Merge historical logs with any existing logs, avoiding duplicates
                        const existingIds = new Set(state.logs.map(l => l.id));
                        const newLogs = historicalLogs.filter((l: LogEntry) => !existingIds.has(l.id));
                        return {
                            logs: [...newLogs.reverse(), ...state.logs].slice(0, 500)
                        };
                    });
                    console.log(`📜 Restored ${historicalLogs.length} logs from backend`);
                    return;
                }
                
                // Bulk Operator Data Update (Main Backend Event) - STATUS ONLY
                if (message.type === 'operator_data_update') {
                    set(state => {
                        const newOperators = { ...state.operators };
                        let hasChanges = false;
                        
                        Object.entries(message.data).forEach(([id, data]: [string, any]) => {
                            const current = newOperators[id];
                            
                            // Only update if status or fatigue actually changed
                            if (!current || 
                                current.fatigue !== data.fatigue ||
                                current.status !== data.status ||
                                current.on_break !== data.on_break ||
                                current.break_requested !== data.break_requested ||
                                current.current_action !== data.current_action ||
                                current.x !== data.x ||
                                current.y !== data.y) {
                                
                                newOperators[id] = {
                                    ...(newOperators[id] || {}), // Keep existing X/Y
                                    ...data,                     // Update status/fatigue
                                };
                                hasChanges = true;
                            }
                        });
                        
                        // Only trigger update if something changed
                        if (!hasChanges) return state;
                        
                        return { 
                            operators: newOperators,
                            activeOperators: newOperators
                        };
                    });
                    return;
                }
                
                // Fog of War Visibility Sync - POSITIONS ONLY
                if (message.type === 'visibility_sync') {
                    set(state => {
                        const newOperators = { ...state.operators };
                        const visibleIds = new Set(message.data.visible_operator_ids);
                        const visibleData = message.data.operators;
                        let hasChanges = false;
                        
                        // Only update operators whose visibility or position changed
                        Object.keys(newOperators).forEach(id => {
                            const current = newOperators[id];
                            const isNowVisible = visibleIds.has(id);
                            const wasVisible = current.visible_to_cameras;
                            
                            if (isNowVisible && visibleData[id]) {
                                // Check if position or visibility changed
                                const newData = visibleData[id];
                                if (current.x !== newData.x || current.y !== newData.y || !wasVisible) {
                                    newOperators[id] = {
                                        ...current,
                                        ...newData,
                                        visible_to_cameras: true
                                    };
                                    hasChanges = true;
                                }
                            } else if (wasVisible && !isNowVisible) {
                                // Only update if visibility changed from true to false
                                newOperators[id] = {
                                    ...current,
                                    visible_to_cameras: false
                                };
                                hasChanges = true;
                            }
                            // If nothing changed, don't create a new object
                        });
                        
                        // Only trigger state update if something actually changed
                        if (hasChanges) {
                            return { operators: newOperators };
                        }
                        return state;
                    });
                    return;
                }

                // Active Operators (Movement - Legacy/Individual)
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
                            [message.data.line_id]: message.data
                        }
                    }));
                    return;
                }

                // Global inventory update
                if (message.type === 'inventory_update') {
                     set({ warehouseInventory: message.data });
                     return;
                }
                
                // Financial update (NEW)
                if (message.type === 'financial_update') {
                    set({ financials: message.data });
                    return;
                }
                
                // KPI update (NEW)
                if (message.type === 'kpi_update') {
                     set({ kpi: message.data });
                     return;
                }
                
                // Conveyor box movement (high frequency)
                if (message.type === 'conveyor_box_update') {
                    // message.data is a single box update, merge into state
                    const box = message.data;
                    set((state) => ({
                        conveyorBoxes: {
                            ...state.conveyorBoxes,
                            [box.id]: box
                        }
                    }));
                    return;
                }
                
                // Box arrived at warehouse - remove from conveyor and update inventory
                if (message.type === 'box_arrived_warehouse') {
                    const { id, product_type, total } = message.data;
                    set((state) => {
                        const newBoxes = { ...state.conveyorBoxes };
                        delete newBoxes[id];
                        return {
                            conveyorBoxes: newBoxes,
                            warehouseInventory: {
                                ...state.warehouseInventory,
                                [product_type]: total
                            }
                        };
                    });
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
                if (['operator_update', 'operator_data_update', 'visibility_sync', 'conveyor_update', 'machine_production_state', 'camera_update', 'supervisor_update', 'operator_fatigue_update', 'shift_status', 'inventory_update', 'line_status', 'maintenance_crew_update'].includes(message.type)) {
                    return;
                }
                
                // Deduplicate Agent Thoughts
                let description = message.data?.thought || JSON.stringify(message.data);
                
                if (message.type === 'agent_thought' || message.type === 'agent_thinking') {
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
        }),
);
