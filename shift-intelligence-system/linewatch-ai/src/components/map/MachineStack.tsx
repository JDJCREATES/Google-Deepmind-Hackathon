import React from 'react';
import { Group, Rect, Circle, Text } from 'react-konva';

// Theme constants
const THEME = {
    machine: {
        body: '#0EA5E9',
        equipment: '#0D9488',
        connector: '#475569',
    },
    status: {
        ok: '#10B981',
        warning: '#F59E0B',
        critical: '#EF4444',
    }
};

interface MachineData {
    id: number;
    label: string;
    x: number;
    y: number;
    machine_w: number;
    machine_h: number;
    equip_w: number;
    equip_h: number;
    connector_h?: number;
    status: string;
    health: number;
}

interface MachineProductionState {
    fill_level: number;
    small_boxes: number;
    product_type: string;
    product_color: string;
    is_running: boolean;
}

interface MachineStackProps {
    machine: MachineData;
    productionState?: MachineProductionState;
}

const MachineStack: React.FC<MachineStackProps> = ({ machine, productionState }) => {
    const { x, y, machine_w: machineW, machine_h: machineH, equip_w: equipW, equip_h: equipH, connector_h: connectorH = 20 } = machine;
    
    // Efficiency/Health Border Color
    let efficiencyColor = THEME.status.ok; // Green (>= 80%)
    if (machine.health < 80) efficiencyColor = '#3B82F6'; // Blue (60-80%)
    if (machine.health < 60) efficiencyColor = THEME.status.warning; // Orange (40-60%)
    if (machine.health < 40) efficiencyColor = THEME.status.critical; // Red (< 40%)

    // Running Status (status indicator dot)
    const isRunning = productionState ? productionState.is_running : machine.status === 'running';
    const runningColor = isRunning ? '#22C55E' : '#64748B'; // Green running, gray stopped
    
    // Production Visuals
    const fillLevel = productionState ? productionState.fill_level : 0;
    const productType = productionState ? productionState.product_type : '';
    const productFillColor = productionState?.product_color || '#3B82F6';

    // Calculate Y positions (stacking upwards)
    const equipX = (machineW - equipW) / 2;
    const equipY = 0;
    const connX = (machineW - 10) / 2;
    const connY = equipH;
    const bodyX = 0;
    const bodyY = equipH + connectorH;
    
    return (
        <Group x={x} y={y}>
             {/* 3. EQUIPMENT (Top) */}
             <Group x={equipX} y={equipY}>
                <Rect 
                    width={equipW} 
                    height={equipH} 
                    fill={THEME.machine.equipment} 
                    cornerRadius={4}
                    shadowBlur={5}
                    shadowColor="#000"
                    shadowOpacity={0.3}
                />
                
                {/* Product Indicator (Fill Level) */}
                {fillLevel > 0 && (
                    <Rect
                        x={2}
                        y={equipH - (equipH * (fillLevel / 100)) + 2} // Fill from bottom
                        width={equipW - 4}
                        height={(equipH * (fillLevel / 100)) - 4}
                        fill={productFillColor}
                        opacity={0.8}
                        cornerRadius={[0, 0, 2, 2]}
                    />
                )}
                
                 <Text 
                    text={productType ? productType.replace('widget_', 'W-').replace('gizmo_', 'G-') : "IDLE"} 
                    fontSize={8} 
                    fill="#FFF" 
                    width={equipW} 
                    align="center" 
                    y={equipH / 2 - 4}
                />
            </Group>

            {/* 2. CONNECTOR (Middle) */}
            <Rect 
                x={connX} 
                y={connY} 
                width={10} 
                height={connectorH} 
                fill={THEME.machine.connector} 
            />

            {/* 1. MACHINE BODY (Base) - NOW WITH EFFICIENCY BORDER */}
            <Rect 
                x={bodyX} 
                y={bodyY} 
                width={machineW} 
                height={machineH} 
                fill={THEME.machine.body} 
                stroke={efficiencyColor}
                strokeWidth={3}
                cornerRadius={2} 
            />
            
            {/* Label */}
            <Text 
                text={machine.label} 
                x={0} 
                y={bodyY + machineH + 5} 
                width={machineW} 
                align="center" 
                fontSize={12} 
                fill="#CBD5E1" 
                fontFamily="Inter, sans-serif"
            />
            
            {/* Status Indicator Dot - Shows RUNNING state (not efficiency) */}
            <Circle 
                x={machineW - 8} 
                y={bodyY + 8} 
                radius={4} 
                fill={runningColor} 
                shadowBlur={isRunning ? 5 : 0} 
                shadowColor={runningColor} 
            />
        </Group>
    );
};

export default MachineStack;
