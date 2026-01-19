import * as React from 'react';
import { motion } from 'framer-motion';
import { Play, Pause, SkipBack, SkipForward, X } from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';

export const TimelineScrubber: React.FC = () => {
    const {
        isReplaying,
        replayTimestamp,
        enterReplayMode,
        exitReplayMode,
        seekToTimestamp,
        getReplayTimeRange,
        replayPlaybackSpeed,
        setReplayPlaybackSpeed,
        state,
    } = useDashboard();

    const [isDragging, setIsDragging] = React.useState(false);
    const [isPlaying, setIsPlaying] = React.useState(false);
    const scrubberRef = React.useRef<HTMLDivElement>(null);

    const timeRange = getReplayTimeRange();

    // Playback animation
    React.useEffect(() => {
        if (!isPlaying || !isReplaying || !timeRange || !replayTimestamp) return;

        const interval = setInterval(() => {
            const newTimestamp = replayTimestamp + (100 * replayPlaybackSpeed);
            if (newTimestamp > timeRange.end) {
                setIsPlaying(false);
                seekToTimestamp(timeRange.end);
            } else {
                seekToTimestamp(newTimestamp);
            }
        }, 100);

        return () => clearInterval(interval);
    }, [isPlaying, isReplaying, replayTimestamp, timeRange, replayPlaybackSpeed, seekToTimestamp]);

    const handleScrubberClick = (e: React.MouseEvent<HTMLDivElement>) => {
        if (!scrubberRef.current || !timeRange) return;

        const rect = scrubberRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = x / rect.width;
        const timestamp = timeRange.start + (timeRange.end - timeRange.start) * percentage;

        seekToTimestamp(timestamp);
    };

    const handleMouseDown = () => {
        setIsDragging(true);
        setIsPlaying(false);
    };

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        if (!isDragging || !scrubberRef.current || !timeRange) return;

        const rect = scrubberRef.current.getBoundingClientRect();
        const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
        const percentage = x / rect.width;
        const timestamp = timeRange.start + (timeRange.end - timeRange.start) * percentage;

        seekToTimestamp(timestamp);
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    React.useEffect(() => {
        if (isDragging) {
            window.addEventListener('mouseup', handleMouseUp);
            return () => window.removeEventListener('mouseup', handleMouseUp);
        }
        return undefined;
    }, [isDragging]);

    const formatTime = (timestamp: number) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { hour12: false });
    };

    const getPlayheadPosition = () => {
        if (!timeRange || !replayTimestamp) return 0;
        const percentage = (replayTimestamp - timeRange.start) / (timeRange.end - timeRange.start);
        return percentage * 100;
    };

    // Extract anomaly events for markers
    const anomalyMarkers = React.useMemo(() => {
        if (!state.mission?.anomalies || !timeRange) return [];
        return state.mission.anomalies.map((anomaly: any) => {
            const anomalyTime = new Date(anomaly.timestamp).getTime();
            const percentage = ((anomalyTime - timeRange.start) / (timeRange.end - timeRange.start)) * 100;
            return { id: anomaly.id, percentage, severity: anomaly.severity };
        });
    }, [state.mission?.anomalies, timeRange]);

    if (!isReplaying) {
        return null;
    }

    return (
        <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="fixed bottom-0 left-0 right-0 bg-black/90 backdrop-blur-xl border-t border-cyan-500/30 p-6 z-50"
        >
            <div className="max-w-7xl mx-auto space-y-4">
                {/* Timeline */}
                <div className="relative">
                    <div
                        ref={scrubberRef}
                        onClick={handleScrubberClick}
                        onMouseMove={handleMouseMove}
                        className="relative h-12 bg-slate-900 rounded-lg border border-cyan-500/20 cursor-pointer overflow-hidden"
                    >
                        {/* Anomaly Markers */}
                        {anomalyMarkers.map((marker) => (
                            <div
                                key={marker.id}
                                className={`absolute top-0 bottom-0 w-1 ${marker.severity === 'Critical' ? 'bg-red-500' : 'bg-yellow-500'
                                    }`}
                                style={{ left: `${marker.percentage}%` }}
                            />
                        ))}

                        {/* Playhead */}
                        <motion.div
                            className="absolute top-0 bottom-0 w-1 bg-cyan-400 shadow-[0_0_10px_#22d3ee]"
                            style={{ left: `${getPlayheadPosition()}%` }}
                            onMouseDown={handleMouseDown}
                        >
                            <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-cyan-400 rounded-full shadow-[0_0_10px_#22d3ee] cursor-grab active:cursor-grabbing" />
                        </motion.div>

                        {/* Time Labels */}
                        {timeRange && (
                            <>
                                <span className="absolute left-2 top-1/2 transform -translate-y-1/2 text-[10px] text-white/40 font-mono">
                                    {formatTime(timeRange.start)}
                                </span>
                                <span className="absolute right-2 top-1/2 transform -translate-y-1/2 text-[10px] text-white/40 font-mono">
                                    {formatTime(timeRange.end)}
                                </span>
                            </>
                        )}
                    </div>

                    {/* Current Time Tooltip */}
                    {replayTimestamp && (
                        <div
                            className="absolute -top-10 bg-cyan-500/20 border border-cyan-500/50 px-3 py-1 rounded text-cyan-400 text-xs font-mono"
                            style={{ left: `${getPlayheadPosition()}%`, transform: 'translateX(-50%)' }}
                        >
                            {formatTime(replayTimestamp)}
                        </div>
                    )}
                </div>

                {/* Controls */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => timeRange && seekToTimestamp(timeRange.start)}
                            className="p-2 bg-slate-800 hover:bg-slate-700 rounded text-cyan-400 transition-colors"
                        >
                            <SkipBack className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setIsPlaying(!isPlaying)}
                            className="p-3 bg-cyan-500/20 hover:bg-cyan-500/30 rounded-lg text-cyan-400 transition-colors"
                        >
                            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                        </button>
                        <button
                            onClick={() => timeRange && seekToTimestamp(timeRange.end)}
                            className="p-2 bg-slate-800 hover:bg-slate-700 rounded text-cyan-400 transition-colors"
                        >
                            <SkipForward className="w-4 h-4" />
                        </button>

                        {/* Speed Control */}
                        <div className="flex items-center gap-2 ml-4">
                            <span className="text-xs text-white/40 uppercase tracking-wider">Speed:</span>
                            {[0.5, 1, 2, 5].map((speed) => (
                                <button
                                    key={speed}
                                    onClick={() => setReplayPlaybackSpeed(speed)}
                                    className={`px-2 py-1 rounded text-xs font-bold transition-colors ${replayPlaybackSpeed === speed
                                        ? 'bg-cyan-500/30 text-cyan-400 border border-cyan-500/50'
                                        : 'bg-slate-800 text-white/40 hover:text-white/60'
                                        }`}
                                >
                                    {speed}x
                                </button>
                            ))}
                        </div>
                    </div>

                    <button
                        onClick={exitReplayMode}
                        className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded-lg text-red-400 font-bold uppercase text-xs tracking-wider transition-all"
                    >
                        <X className="w-4 h-4" />
                        Exit Replay
                    </button>
                </div>
            </div>
        </motion.div>
    );
};
