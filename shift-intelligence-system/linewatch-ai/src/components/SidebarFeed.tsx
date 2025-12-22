import React, { useEffect, useRef } from 'react';
import { useStore } from '../store/useStore';
import clsx from 'clsx';
// USING REACT ICONS AS REQUESTED (NO LUCIDE)
import { FaRobot, FaVideo, FaExclamationTriangle, FaCogs } from 'react-icons/fa'; 
import { MdOutlinePsychology } from 'react-icons/md';

const SidebarFeed: React.FC = () => {
    const { logs } = useStore();
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div className="flex flex-col h-full bg-white border border-stone-200 rounded-md shadow-sm overflow-hidden">
            <div className="p-3 bg-primary-50 border-b border-primary-100 flex items-center gap-2">
                <MdOutlinePsychology className="text-primary-700 text-xl" />
                <h2 className="font-bold text-stone-800 text-sm">NEURAL STREAM</h2>
            </div>
            
            <div className="flex-1 overflow-y-auto p-2 space-y-2 scrollbar-default bg-stone-50">
                {logs.length === 0 && (
                    <div className="text-center text-stone-400 mt-10 text-xs italic">
                        Waiting for neural signals...
                    </div>
                )}
                
                {logs.map((log, i) => (
                    <LogItem key={i} log={log} />
                ))}
                <div ref={bottomRef} />
            </div>
        </div>
    );
};

const LogItem: React.FC<{ log: string }> = ({ log }) => {
    // Basic parsing to determine icon/color
    let Icon = FaRobot;
    let colorClass = "text-stone-600 bg-white border-stone-200";
    
    if (log.includes('visual_signal')) {
        Icon = FaVideo;
        colorClass = "text-blue-700 bg-blue-50 border-blue-100";
    } else if (log.includes('risk') || log.includes('CRITICAL')) {
        Icon = FaExclamationTriangle;
        colorClass = "text-red-700 bg-red-50 border-red-100";
    } else if (log.includes('production_signal')) {
        Icon = FaCogs;
        colorClass = "text-amber-700 bg-amber-50 border-amber-100";
    }

    // Strip timestamp for display if needed, or keep it
    const parts = log.split('] ');
    const time = parts[0] + ']';
    const msg = parts[1] || log;

    return (
        <div className={clsx("p-2 rounded text-xs border flex gap-2 items-start", colorClass)}>
            <div className="mt-0.5 opacity-70"><Icon /></div>
            <div>
                <span className="font-mono opacity-50 mr-1 text-[10px]">{time}</span>
                <span className="leading-tight">{msg}</span>
            </div>
        </div>
    );
};

export default SidebarFeed;
