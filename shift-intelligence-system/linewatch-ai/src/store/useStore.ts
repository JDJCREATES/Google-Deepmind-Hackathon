import { create } from 'zustand';
import type { FloorLayout, Line } from '../types';
import { api, WS_URL } from '../services/api';

interface State {
    // Static Data
    layout: FloorLayout | null;
    isLoading: boolean;
    error: string | null;

    // Live Data
    socket: WebSocket | null;
    isConnected: boolean;
    logs: string[];

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
            get().logs.push('Connected to Agent system');
        };

        socket.onclose = () => {
            set({ isConnected: false, socket: null });
            // Reconnect logic could go here
        };

        socket.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleIncomingMessage(set, get, msg);
        };

        set({ socket });
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
    
    const AGENT_TYPES = ['agent_thought', 'agent_decision', 'agent_reasoning', 'hypothesis', 'evidence', 'belief', 'action'];
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
    
    if (SIMULATION_NOISE.includes(msg.type)) {
        return; // Skip entirely
    }
    
    // Build log line for AGENT REASONING ONLY
    let logLine = '';
    
    // Highlight agent thoughts with clear prefix
    if (AGENT_TYPES.includes(msg.type)) {
        const agentName = msg.data?.source || 'Agent';
        logLine = `[${timestamp}] 🤖 ${agentName}: ${msg.data?.description || msg.type}`;
    } 
    // System alerts (critical only)
    else if (SYSTEM_TYPES.includes(msg.type)) {
        logLine = `[${timestamp}] ⚙️ SYSTEM: ${msg.data?.description || msg.type}`;
    }
    // Default: mark as unfiltered but show
    else {
        logLine = `[${timestamp}] ${msg.type}`;
        if (msg.data?.description) {
            logLine += `: ${msg.data.description}`;
        } else if (msg.data?.source) {
            logLine += ` from ${msg.data.source}`;
        }
    }
    
    // Only add to logs if we built a line
    if (logLine) {
        set((state: any) => ({
            logs: [logLine, ...state.logs].slice(0, 50) // Keep last 50
        }));
    }
}

