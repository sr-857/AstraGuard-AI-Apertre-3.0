import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, AlertTriangle } from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';

export const ReplayOverlay: React.FC = () => {
    const { isReplaying, replayTimestamp } = useDashboard();

    const formatTimestamp = (timestamp: number) => {
        const date = new Date(timestamp);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        });
    };

    return (
        <AnimatePresence>
            {isReplaying && (
                <>
                    {/* Sepia Overlay */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-amber-900/10 pointer-events-none z-40 backdrop-sepia"
                        style={{
                            backdropFilter: 'sepia(0.3) contrast(0.9)',
                            WebkitBackdropFilter: 'sepia(0.3) contrast(0.9)',
                        }}
                    />

                    {/* Top Banner */}
                    <motion.div
                        initial={{ y: -100, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: -100, opacity: 0 }}
                        className="fixed top-0 left-0 right-0 z-50 pointer-events-none"
                    >
                        <div className="bg-gradient-to-b from-amber-900/80 to-transparent backdrop-blur-sm border-b-2 border-amber-500/50 p-4">
                            <div className="max-w-7xl mx-auto flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/20 border border-amber-500/50 rounded-lg">
                                        <Clock className="w-5 h-5 text-amber-400 animate-pulse" />
                                        <span className="text-amber-400 font-bold uppercase text-sm tracking-widest">
                                            Replay Mode
                                        </span>
                                    </div>

                                    {replayTimestamp && (
                                        <div className="px-4 py-2 bg-black/40 border border-amber-500/30 rounded-lg">
                                            <span className="text-amber-300 font-mono text-sm">
                                                {formatTimestamp(replayTimestamp)}
                                            </span>
                                        </div>
                                    )}
                                </div>

                                <div className="flex items-center gap-2 px-4 py-2 bg-red-500/20 border border-red-500/50 rounded-lg">
                                    <AlertTriangle className="w-4 h-4 text-red-400" />
                                    <span className="text-red-400 font-bold uppercase text-xs tracking-wider">
                                        Historical Data - Not Live
                                    </span>
                                </div>
                            </div>
                        </div>
                    </motion.div>

                    {/* Corner Watermark */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed bottom-32 right-6 z-40 pointer-events-none"
                    >
                        <div className="text-amber-500/30 font-mono text-6xl font-bold transform rotate-12">
                            REPLAY
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};
