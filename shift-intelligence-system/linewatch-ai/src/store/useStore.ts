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
            get().logs.push('Connected to Neural Stream');
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
            await api.simulation.start();
        } catch(e) { console.error(e) }
    }
}));

function handleIncomingMessage(set: any, get: any, msg: any) {
    const timestamp = new Date().toLocaleTimeString();
    
    // FILTER: Skip noisy messages from the log stream
    const NOISY_TYPES = ['line_status', 'simulation_tick'];
    
    if (msg.type === 'line_status') {
         // Update line health silently (no log)
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
         return; // Don't add to logs
    }
    
    if (msg.type === 'simulation_tick') {
        return; // Skip tick messages entirely
    }
    
    // Build log line for interesting messages
    let logLine = `[${timestamp}] ${msg.type}`;
    
    if (msg.data?.description) {
        logLine += `: ${msg.data.description}`;
    } else if (msg.data?.source) {
        logLine += ` from ${msg.data.source}`;
    }
    
    set((state: any) => ({
        logs: [logLine, ...state.logs].slice(0, 30) // Keep last 30
    }));
}
