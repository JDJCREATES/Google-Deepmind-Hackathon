import { create } from 'zustand';
import type { FloorLayout } from '../types';
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
    thoughtSignatures: Record<string, number>;  // Per-agent signature counts

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
    thoughtSignatures: {},

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
                
                // Skip line_status messages - they're just noise for the Activity Log
                if (message.type === 'line_status') {
                    return;
                }
                
                // Handle thought signature events
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
                
                // Create structured log entry
                const logEntry: LogEntry = {
                    id: `log-${Date.now()}-${Math.random()}`,
                    type: message.type || 'unknown',
                    source: message.data?.source || message.data?.agent || 'System',
                    description: message.data?.description || message.data?.thought || JSON.stringify(message.data),
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
