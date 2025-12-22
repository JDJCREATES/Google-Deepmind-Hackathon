export interface Zone {
    id: string;
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
    color: string;
    type?: string;
}

export interface Line {
    id: number;
    label: string;
    x: number;
    y: number;
    width: number;
    height: number;
    orientation: 'horizontal' | 'vertical';
    status: 'operational' | 'down' | 'maintenance' | 'bottleneck';
}

export interface Camera {
    id: string;
    line_id: number;
    x: number;
    y: number;
    rotation: number;
    fov: number;
    range: number;
    label: string;
    is_alerting?: boolean;
}

export interface FloorLayout {
    dimensions: {
        width: number;
        height: number;
    };
    zones: Zone[];
    lines: Line[];
    cameras: Camera[];
}

export interface SimulationStatus {
    running: boolean;
    uptime_minutes: number;
    tick_rate: number;
}
