import React, { useRef, useEffect } from 'react';
import { Group, Circle, Wedge } from 'react-konva';
import Konva from 'konva';

// Theme constants
const THEME = {
    camera: {
        body: '#64748B',
        active: '#3B82F6',
        detecting: '#EF4444',
        fov: 'rgba(59, 130, 246, 0.15)', // Blue-ish tint
        fovDetected: 'rgba(239, 68, 68, 0.25)', // Red-ish tint
    },
};

interface CameraData {
    id: string;
    label: string;
    x: number;
    y: number;
    rotation: number;     // e.g. 45 degrees
    fov?: number;        // e.g. 60 degrees
    range?: number;      // e.g. 150px
    status?: string;     // 'active' | 'detecting' | 'idle'
    detection_count?: number;
    color?: string;      // Dynamic color from backend
}

const CameraComp: React.FC<{ camera: CameraData }> = ({ camera }) => {
    // Default values if not provided
    const fov = camera.fov || 60;
    const range = camera.range || 200;
    const isDetecting = camera.status === 'detecting';
    
    // Animation ref for pulsing effect when detecting
    const wedgeRef = useRef<Konva.Wedge>(null);
    
    useEffect(() => {
        if (isDetecting && wedgeRef.current) {
             const anim = new Konva.Animation((frame) => {
                if (!frame) return;
                const scale = 1 + Math.sin(frame.time / 400) * 0.02;
                wedgeRef.current?.scale({ x: scale, y: scale });
            }, wedgeRef.current.getLayer());
            
            anim.start();
            return () => { anim.stop(); };
        } else if (wedgeRef.current) {
            wedgeRef.current.scale({ x: 1, y: 1 });
        }
    }, [isDetecting]);

    return (
        <Group x={camera.x} y={camera.y}>
            {/* FOV Cone (Vision) */}
            <Wedge
                ref={wedgeRef}
                radius={range}
                angle={fov}
                rotation={camera.rotation - fov / 2} // Center the FOV on the rotation angle
                fill={isDetecting ? THEME.camera.fovDetected : THEME.camera.fov}
                stroke={isDetecting ? (camera.color || THEME.camera.detecting) : THEME.camera.active}
                strokeWidth={1}
                opacity={0.5}
                listening={false} // Don't block clicks
            />
            
            {/* Camera Body Icon */}
            <Group rotation={camera.rotation}>
                <Circle
                    radius={6}
                    fill={THEME.camera.body}
                    stroke="#1E293B"
                    strokeWidth={1}
                />
                {/* Lens */}
                <Circle
                    x={3}
                    radius={3}
                    fill={isDetecting ? (camera.color || THEME.camera.detecting) : '#000'}
                />
            </Group>
        </Group>
    );
};

export default CameraComp;
