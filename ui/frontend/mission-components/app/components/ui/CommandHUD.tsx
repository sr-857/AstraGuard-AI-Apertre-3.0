'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

export const CommandHUD: React.FC = () => {
    const [scanPos, setScanPos] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setScanPos(prev => (prev + 0.5) % 100);
        }, 50);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="fixed inset-0 pointer-events-none z-[100] overflow-hidden">
            {/* Scanning Line */}
            <motion.div
                className="absolute w-full h-[2px] bg-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.5)]"
                style={{ top: `${scanPos}%` }}
            />

            {/* Corners - Top Left */}
            <div className="absolute top-4 left-4 w-32 h-32 border-t-2 border-l-2 border-cyan-500/30">
                <div className="absolute top-2 left-2 flex flex-col gap-1">
                    <div className="w-16 h-[2px] bg-cyan-500/50" />
                    <div className="text-[8px] font-mono text-cyan-500/70 tracking-tighter uppercase">HUD_V3.8_SYSLOG</div>
                </div>
            </div>

            {/* Corners - Top Right */}
            <div className="absolute top-4 right-4 w-32 h-32 border-t-2 border-r-2 border-cyan-500/30">
                <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                    <div className="w-16 h-[2px] bg-cyan-500/50" />
                    <div className="text-[8px] font-mono text-cyan-500/70 tracking-tighter uppercase">SIG_STRENGTH_98%</div>
                </div>
            </div>

            {/* Corners - Bottom Left */}
            <div className="absolute bottom-4 left-4 w-32 h-32 border-b-2 border-l-2 border-cyan-500/30">
                <div className="absolute bottom-2 left-2 flex flex-col gap-1">
                    <div className="text-[8px] font-mono text-cyan-500/70 tracking-tighter uppercase">COORD_SYS: WGS84</div>
                    <div className="w-16 h-[2px] bg-cyan-500/50" />
                </div>
            </div>

            {/* Corners - Bottom Right */}
            <div className="absolute bottom-4 right-4 w-32 h-32 border-b-2 border-r-2 border-cyan-500/30">
                <div className="absolute bottom-2 right-2 flex flex-col items-end gap-1">
                    <div className="text-[8px] font-mono text-cyan-500/70 tracking-tighter uppercase">AUTH_TOKEN: VALID</div>
                    <div className="w-16 h-[2px] bg-cyan-500/50" />
                </div>
            </div>

            {/* Vignette Effect */}
            <div className="absolute inset-0 bg-radial-vignette opacity-20 pointer-events-none" />

            {/* HUD Noise Effect */}
            <div className="absolute inset-0 opacity-[0.03] pointer-events-none mix-blend-overlay bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
        </div>
    );
};
