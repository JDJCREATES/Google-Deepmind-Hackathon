import React from 'react';
import { Group, Rect, Text } from 'react-konva';

// Theme constants
const THEME = {
    conveyor: {
        belt: '#64748B',
        running: '#10B981',
        stopped: '#EF4444',
    },
};

interface ConveyorData {
    id: string;
    x: number;
    y: number;
    width: number;
    height: number;
    direction: string;
    status: string;
}

const ConveyorComp: React.FC<{ conveyor: ConveyorData }> = ({ conveyor }) => {
    const isRunning = conveyor.status === 'running';
    const statusColor = isRunning ? THEME.conveyor.running : THEME.conveyor.stopped;
    const isVertical = conveyor.direction === 'vertical';

    return (
        <Group x={conveyor.x} y={conveyor.y}>
            {/* Belt background */}
            <Rect
                width={conveyor.width}
                height={conveyor.height}
                fill={THEME.conveyor.belt}
                cornerRadius={2}
            />
            
            {/* Status indicator line */}
            <Rect
                x={0}
                y={0}
                width={isVertical ? 3 : conveyor.width}
                height={isVertical ? conveyor.height : 3}
                fill={statusColor}
                cornerRadius={1}
            />
            
            {/* Direction arrows (visual hint) */}
            {isRunning && !isVertical && (
                <Group>
                    {Array.from({ length: Math.floor(conveyor.width / 60) }).map((_, i) => (
                        <Text
                            key={i}
                            x={conveyor.width - 20 - i * 60}
                            y={conveyor.height / 2 - 4}
                            text="◀"
                            fontSize={8}
                            fill="#94A3B8"
                            opacity={0.5}
                        />
                    ))}
                </Group>
            )}
        </Group>
    );
};

export default ConveyorComp;
