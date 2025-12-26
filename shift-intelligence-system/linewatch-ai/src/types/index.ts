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
    orientation?: 'horizontal' | 'vertical';
    status: string;
    // Backend properties
    machine_w: number;
    machine_h: number;
    equip_w: number;
    equip_h: number;
    connector_h?: number;
    health: number;
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
    status: string;
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
    conveyors: any[]; // Extended layout
    operators: any[]; // Extended layout
}

export interface SimulationStatus {
    running: boolean;
    uptime_minutes: number;
    tick_rate: number;
}
