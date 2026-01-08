import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';

interface HighContrastOverlayProps {
    isActive: boolean;
    missedAlerts: number;
    onAcknowledge: () => void;
}

export const HighContrastOverlay: React.FC<HighContrastOverlayProps> = ({
    isActive,
    missedAlerts,
    onAcknowledge,
}) => {
    React.useEffect(() => {
        if (isActive) {
            // Play warning sound
            const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = 800; // High-pitched warning
            oscillator.type = 'sine';
            gainNode.gain.value = 0.1;

            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.3);
        }
    }, [isActive]);

    if (!isActive) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-[100] pointer-events-none"
            >
                {/* Pulsing Border */}
                <motion.div
                    className="absolute inset-0 border-8 border-yellow-400"
                    animate={{
                        opacity: [0.5, 1, 0.5],
                        borderWidth: ['8px', '12px', '8px'],
                    }}
                    transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />

                {/* Yellow Tint Overlay */}
                <div className="absolute inset-0 bg-yellow-400/10" />

                {/* Warning Message */}
                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-auto">
                    <motion.div
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="bg-yellow-500/20 backdrop-blur-xl border-4 border-yellow-400 rounded-xl p-6 max-w-md"
                    >
                        <div className="flex items-center gap-4 mb-4">
                            <motion.div
                                animate={{ rotate: [0, 10, -10, 0] }}
                                transition={{ duration: 0.5, repeat: Infinity }}
                            >
                                <AlertTriangle className="w-12 h-12 text-yellow-400" />
                            </motion.div>
                            <div>
                                <h2 className="text-2xl font-bold text-yellow-400 uppercase tracking-wider">
                                    ATTENTION REQUIRED
                                </h2>
                                <p className="text-sm text-white/80">Operator Focus Alert</p>
                            </div>
                        </div>

                        <p className="text-white mb-4">
                            You have missed <span className="font-bold text-yellow-400">{missedAlerts} alert{missedAlerts !== 1 ? 's' : ''}</span>.
                            Please acknowledge to continue monitoring.
                        </p>

                        <button
                            onClick={onAcknowledge}
                            className="w-full px-4 py-3 bg-yellow-500 hover:bg-yellow-400 text-black font-bold uppercase tracking-wider rounded-lg transition-colors"
                        >
                            I'm Alert - Resume Monitoring
                        </button>
                    </motion.div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
