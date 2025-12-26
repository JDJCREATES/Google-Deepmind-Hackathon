import React, { useEffect, useRef } from 'react';
import { Group, Rect, Text, Circle } from 'react-konva';
import Konva from 'konva';

// Theme constants
const THEME = {
    operator: {
        active: '#22C55E',
        idle: '#F59E0B',
        moving: '#0EA5E9',
        inspecting: '#10B981',
    },
};

interface OperatorProps {
    operator: {
        id: string;
        name: string;
        x: number;
        y: number;
        status: string;
    }
}

const OperatorComp: React.FC<OperatorProps> = ({ operator }) => {
    // Fatigue Logic (safe access)
    const fatigue = (operator as any).fatigue || 0;
    const efficiency = 100 - fatigue;
    const onBreak = (operator as any).on_break;
    
    // Status Bar Config
    const barWidth = 30;
    const barHeight = 4;
    const fillWidth = (efficiency / 100) * barWidth;
    
    // Color based on efficiency level
    let barColor = '#10B981'; // Green
    if (efficiency < 60) barColor = '#F59E0B'; // Amber
    if (efficiency < 30) barColor = '#EF4444'; // Red

    const groupRef = useRef<any>(null);
    
    useEffect(() => {
        if (!groupRef.current) return;
        
        groupRef.current.to({
            x: operator.x,
            y: operator.y,
            duration: 0.5, // Sync with backend tick
            easing: Konva.Easings.Linear,
        });
    }, [operator.x, operator.y]);

    let fillColor = THEME.operator.idle;
    if (operator.status === 'moving') fillColor = THEME.operator.moving;
    if (operator.status === 'working') fillColor = THEME.operator.active;
    if (operator.status === 'inspecting') fillColor = THEME.operator.inspecting;
    
    // Use stored color if available (for precise visual sync)
    // NOTE: This might be redundant if we just map status correctly
    
    return (
        <Group 
            ref={groupRef}
            x={operator.x}
            y={operator.y}
        >
            {/* Outer ring (selection/status) */}
            <Circle 
                radius={12} 
                stroke={fillColor} 
                strokeWidth={2} 
                opacity={0.6}
            />
            {/* Main body */}
            <Circle 
                radius={8} 
                fill={fillColor} 
                opacity={0.9} 
                stroke="#FFF" 
                strokeWidth={1}
                shadowColor={fillColor} 
                shadowBlur={10} 
                shadowOpacity={0.7} 
            />
            
            {/* Status Bar (Fatigue) */}
            {!onBreak ? (
                <Group y={-22}>
                    {/* Background */}
                    <Rect x={-barWidth / 2} y={0} width={barWidth} height={barHeight} fill="#1E293B" cornerRadius={2} stroke="#475569" strokeWidth={0.5} />
                    {/* Fill */}
                    <Rect x={-barWidth / 2} y={0} width={fillWidth} height={barHeight} fill={barColor} cornerRadius={2} />
                </Group>
            ) : (
                 <Group y={-22}>
                    <Rect x={-12} y={0} width={24} height={10} fill="#0EA5E9" cornerRadius={2} opacity={0.8} />
                    <Text text="BREAK" fontSize={6} fill="#FFF" x={-12} y={2} width={24} align="center" fontFamily="Inter" fontStyle="bold"/>
                 </Group>
            )}

            {/* Name Label */}
            <Text 
                text={operator.name} 
                fontSize={10} 
                fontFamily="Inter, sans-serif" 
                fill="#E2E8F0" 
                y={14} 
                x={-30} 
                width={60} 
                align="center" 
            />
        </Group>
    );
};

export default OperatorComp;
