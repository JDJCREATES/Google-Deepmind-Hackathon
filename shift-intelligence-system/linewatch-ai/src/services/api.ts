import axios from 'axios';
import type { FloorLayout, SimulationStatus } from '../types';
import { config } from '../config';

const API_BASE = `${config.API_URL}/api`;

export const api = {
    layout: {
        get: async (): Promise<FloorLayout> => {
            const { data } = await axios.get<FloorLayout>(`${API_BASE}/simulation/layout`);
            return data;
        }
    },
    simulation: {
        getStatus: async (): Promise<SimulationStatus> => {
            const { data } = await axios.get<SimulationStatus>(`${API_BASE}/simulation/status`);
            return data;
        },
        start: async () => axios.post(`${API_BASE}/simulation/start`),
        stop: async () => axios.post(`${API_BASE}/simulation/stop`),
        injectEvent: async (type: string) => axios.post(`${API_BASE}/simulation/event`, { event_type: type })
    }
};

// WebSocket URL
export const WS_URL = `${config.WS_URL}/ws/stream`;
