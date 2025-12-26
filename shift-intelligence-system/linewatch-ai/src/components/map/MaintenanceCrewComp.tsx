import React, { useRef, useEffect } from 'react';
import { Group, Rect, Circle, Text } from 'react-konva';
import Konva from 'konva';

// Theme constants
const THEME = {
    crew: {
        idle: '#F97316',      // Orange
        moving: '#FB923C',    // Lighter Orange
        repairing: '#EA580C', // Dark Orange
        helmet: '#FFF',
    },
};

interface MaintenanceCrewProps {
    crew: {
        x: number;
        y: number;
        status: string; // 'idle', 'moving_to_machine', 'working', 'returning'
        current_action: string;
    }
}

const MaintenanceCrewComp: React.FC<MaintenanceCrewProps> = ({ crew }) => {
    const groupRef = useRef<any>(null);
    
    // IMMEDIATE position update (no animation) to prevent ghost movement
    useEffect(() => {
        if (!groupRef.current) return;
        groupRef.current.position({ x: crew.x, y: crew.y });
    }, [crew.x, crew.y]);

    let fillColor = THEME.crew.idle;
    if (crew.status === 'moving_to_machine' || crew.status === 'returning') fillColor = THEME.crew.moving;
    if (crew.status === 'working') fillColor = THEME.crew.repairing;
    
    // Safety check for invalid coordinates
    if (typeof crew.x !== 'number' || typeof crew.y !== 'number' || isNaN(crew.x) || isNaN(crew.y)) {
        return null;
    }
    
    return (
        <Group 
            ref={groupRef}
            x={crew.x}
            y={crew.y}
        >
            {/* Outer Glow for visibility */}
            <Circle 
                radius={14} 
                stroke={fillColor} 
                strokeWidth={2} 
                opacity={0.4}
                fill={fillColor} 
                fillOpacity={0.1}
            />
            
            {/* Body (Square for distinction from Operators) */}
            <Rect 
                x={-9}
                y={-9}
                width={18}
                height={18}
                fill={fillColor} 
                cornerRadius={4}
                shadowColor={fillColor}
                shadowBlur={8}
                shadowOpacity={0.6}
            />
            
            {/* Helmet (White Band) */}
            <Rect
                x={-9}
                y={-9}
                width={18}
                height={6}
                fill={THEME.crew.helmet}
                cornerRadius={[4, 4, 0, 0]}
                opacity={0.9}
            />
            
            {/* Wrench Icon (implied by cross?) or Text */}
            <Text 
                text="🔧" 
                fontSize={10} 
                x={-5} 
                y={-4} 
                opacity={0.9}
            />

            {/* Status Label */}
            <Group y={16}>
                <Rect x={-25} width={50} height={12} fill="#1E293B" opacity={0.8} cornerRadius={4} />
                <Text 
                    text={crew.status.toUpperCase().replace('_', ' ')} 
                    fontSize={8} 
                    fontFamily="Inter, sans-serif" 
                    fill="#FDBA74" 
                    width={50}
                    y={2}
                    align="center" 
                />
            </Group>
        </Group>
    );
};

export default MaintenanceCrewComp;
