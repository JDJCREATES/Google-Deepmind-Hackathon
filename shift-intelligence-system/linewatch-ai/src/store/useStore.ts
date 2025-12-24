import { create } from 'zustand';
import type { FloorLayout, Line } from '../types';
import { api, WS_URL } from '../services/api';

export interface LogEntry {
    id: string;
    timestamp: string;
    type: string;
    source?: string;
    description?: string;
    data?: any;
}

interface State {
    // Static Data
    layout: FloorLayout | null;
    isLoading: boolean;
    error: string | null;

    // Live Data
    socket: WebSocket | null;
    isConnected: boolean;
    logs: LogEntry[];

    // Actions
    fetchLayout: () => Promise<void>;
    connectWebSocket: () => void;
    
    // Manual Controls
    toggleSimulation: () => Promise<void>;
}

export const useStore = create<State>((set, get) => ({
    layout: null,
    isLoading: false,
    error: null,
    socket: null,
    isConnected: false,
    logs: [],

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
            // Optional: push a system entry if needed, or just leave it empty
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
                
                // Create structured log entry
                const logEntry: LogEntry = {
                    id: `log-${Date.now()}-${Math.random()}`,
                    type: message.type || 'unknown',
                    source: message.data?.source || 'System',
                    description: message.data?.description || JSON.stringify(message.data),
                    timestamp: message.data?.timestamp || new Date().toISOString(),
                    data: message.data,
                };

                set((state) => ({
                    logs: [logEntry, ...state.logs].slice(0, 100), // Keep last 100
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
            console.log('[DEBUG] toggleSimulation called');
            const status = await api.simulation.getStatus();
            console.log('[DEBUG] Current simulation status:', status);
            
            if (status.running) {
                console.log('[DEBUG] Calling stop...');
                await api.simulation.stop();
                console.log('[DEBUG] Stop call complete');
            } else {
                console.log('[DEBUG] Calling start...');
                await api.simulation.start();
                console.log('[DEBUG] Start call complete');
            }
        } catch(e) { 
            console.error('[DEBUG] Failed to toggle simulation:', e);
        }
    }
}));

function handleIncomingMessage(set: any, get: any, msg: any) {
    const timestamp = new Date().toLocaleTimeString();
    
    // ===== PRIORITY: Show ONLY Agent Reasoning & AI Thinking =====
    // Filter OUT all simulation/input data - we want to showcase the AI, not the fake data
    
    // Key event types we want to show rich details for
    const VISIBLE_TYPES = [
        'agent_thought', 
        'agent_decision', 
        'agent_reasoning', 
        'hypothesis', 
        'hypotheses_generated', 
        'evidence', 
        'belief', 
        'action', 
        'investigation_start',
        'visual_signal',
        'reasoning_phase'
    ];
    
    const SYSTEM_TYPES = ['system_alert', 'system_status'];
    
    // Silently update line health without logging
    if (msg.type === 'line_status') {
         const { layout } = get();
         if (layout) {
             const updatedLines = layout.lines.map((l: Line) => {
                 if (l.id === msg.data.line_id) {
                     return { ...l, health: msg.data.health };
                 }
                 return l;
             });
             set({ layout: { ...layout, lines: updatedLines } });
         }
         return; // Don't log
    }
    
    // HIDE all simulation noise (input data, ticks, events)
    const SIMULATION_NOISE = [
        'simulation_tick', 
        'simulation_event',
        'line_update',
        'production_signal',
        'sensor_data',
        'system_status'  // Hide system status updates
    ];
    
    // If it's pure noise, skip
    if (SIMULATION_NOISE.includes(msg.type)) {
        // Exception: Show CRITICAL events in a special way if needed, 
        // but generally we want to see the AGENT'S reaction to them, not the event itself.
        // For 'visual_signal' (smoke detected), we DO want to show it.
        if (msg.type !== 'visual_signal') return;
    }
    
    // Create Structured Log Entry
    const newEntry: LogEntry = {
        id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        timestamp,
        type: msg.type,
        source: msg.data?.source || 'System',
        description: msg.data?.description || msg.type,
        data: msg.data
    };
    
    // Only add to logs if it's a type we care about regarding Agents/AI
    // Or if it's explicitly an alert
    if (VISIBLE_TYPES.includes(msg.type) || SYSTEM_TYPES.includes(msg.type) || msg.type === 'visual_signal') {
        set((state: any) => ({
            logs: [newEntry, ...state.logs].slice(0, 50) // Keep last 50
        }));
    }
}

