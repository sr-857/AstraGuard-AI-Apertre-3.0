import * as React from 'react';
import { motion, useMotionValue, useTransform, PanInfo } from 'framer-motion';
import { AlertTriangle, Power } from 'lucide-react';
import { useLongPress } from '../../hooks/useLongPress';

interface RedPhoneResetProps {
    onResetConfirm: () => void;
}

export const RedPhoneReset: React.FC<RedPhoneResetProps> = ({ onResetConfirm }) => {
    const [isCoverOpen, setIsCoverOpen] = React.useState(false);
    const [showConfirmation, setShowConfirmation] = React.useState(false);
    const audioContextRef = React.useRef<AudioContext | null>(null);
    const chargeUpSourceRef = React.useRef<OscillatorNode | null>(null);

    const coverY = useMotionValue(0);
    const coverRotation = useTransform(coverY, [0, -100], [0, -90]);

    // Initialize Web Audio API
    React.useEffect(() => {
        if (typeof window !== 'undefined') {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        return () => {
            audioContextRef.current?.close();
        };
    }, []);

    const playCoverFlip = () => {
        const ctx = audioContextRef.current;
        if (!ctx) return;

        // Mechanical latch sound (short click)
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.frequency.setValueAtTime(200, ctx.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.1);

        gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);

        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + 0.1);
    };

    const playChargeUp = () => {
        const ctx = audioContextRef.current;
        if (!ctx) return;

        // Low-frequency ramp (3 seconds)
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.frequency.setValueAtTime(50, ctx.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 3);

        gainNode.gain.setValueAtTime(0.2, ctx.currentTime);
        gainNode.gain.setValueAtTime(0.4, ctx.currentTime + 3);

        oscillator.start(ctx.currentTime);
        chargeUpSourceRef.current = oscillator;
    };

    const stopChargeUp = () => {
        if (chargeUpSourceRef.current) {
            chargeUpSourceRef.current.stop();
            chargeUpSourceRef.current = null;
        }
    };

    const playHeavyThud = () => {
        const ctx = audioContextRef.current;
        if (!ctx) return;

        // Deep bass impact
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        const filter = ctx.createBiquadFilter();

        oscillator.connect(filter);
        filter.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.frequency.setValueAtTime(40, ctx.currentTime);
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(100, ctx.currentTime);

        gainNode.gain.setValueAtTime(0.8, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + 0.5);
    };

    const longPress = useLongPress({
        threshold: 3000,
        onStart: () => {
            playChargeUp();
        },
        onFinish: () => {
            stopChargeUp();
            playHeavyThud();
            setShowConfirmation(true);
        },
        onCancel: () => {
            stopChargeUp();
        },
    });

    const handleCoverDragEnd = (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
        if (info.offset.y < -50) {
            setIsCoverOpen(true);
            coverY.set(-100);
            playCoverFlip();
        } else {
            setIsCoverOpen(false);
            coverY.set(0);
        }
    };

    const handleCloseCover = () => {
        setIsCoverOpen(false);
        coverY.set(0);
        playCoverFlip();
    };

    const handleConfirmReset = () => {
        onResetConfirm();
        setShowConfirmation(false);
        setIsCoverOpen(false);
        coverY.set(0);
    };

    return (
        <>
            <div className="relative">
                {/* Cover */}
                <motion.div
                    drag={!isCoverOpen ? 'y' : false}
                    dragConstraints={{ top: -60, bottom: 0 }}
                    dragElastic={0.1}
                    onDragEnd={handleCoverDragEnd}
                    style={{
                        y: coverY,
                        rotateX: coverRotation,
                        transformOrigin: 'top center',
                        transformStyle: 'preserve-3d',
                    }}
                    className="absolute inset-0 bg-gradient-to-b from-red-900 to-red-950 border-2 border-red-700 rounded-lg cursor-grab active:cursor-grabbing z-10 w-14 h-14"
                >
                    <div className="flex items-center justify-center h-full">
                        <AlertTriangle className="w-6 h-6 text-red-400" />
                    </div>
                </motion.div>

                {/* Reset Button */}
                <div className="relative w-14 h-14 bg-black border-2 border-red-900 rounded-lg overflow-hidden">
                    {isCoverOpen && (
                        <motion.button
                            {...(() => {
                                const { isPressed, progress, ...handlers } = longPress;
                                return handlers;
                            })()}
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            className="relative w-full h-full bg-gradient-to-br from-red-600 to-red-800 flex items-center justify-center group"
                        >
                            {/* Progress Ring */}
                            {longPress.isPressed && (
                                <svg className="absolute inset-0 w-full h-full -rotate-90">
                                    <circle
                                        cx="50%"
                                        cy="50%"
                                        r="45%"
                                        fill="none"
                                        stroke="rgba(255, 255, 255, 0.3)"
                                        strokeWidth="2"
                                    />
                                    <motion.circle
                                        cx="50%"
                                        cy="50%"
                                        r="45%"
                                        fill="none"
                                        stroke="#fff"
                                        strokeWidth="2"
                                        strokeDasharray="283"
                                        strokeDashoffset={283 - (283 * longPress.progress) / 100}
                                        strokeLinecap="round"
                                    />
                                </svg>
                            )}

                            {/* Button Icon */}
                            <Power
                                className={`w-6 h-6 text-white transition-all ${longPress.isPressed ? 'scale-110' : 'group-hover:scale-105'
                                    }`}
                            />

                            {/* Glow Effect */}
                            <div
                                className={`absolute inset-0 bg-red-500 opacity-0 blur-xl transition-opacity ${longPress.isPressed ? 'opacity-50 animate-pulse' : ''
                                    }`}
                            />
                        </motion.button>
                    )}

                    {isCoverOpen && (
                        <button
                            onClick={handleCloseCover}
                            className="absolute -top-1 -right-1 p-1 text-[10px] text-red-400 hover:text-red-300"
                        >
                            ✕
                        </button>
                    )}
                </div>
            </div>

            {/* Confirmation Modal */}
            {showConfirmation && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50"
                >
                    <motion.div
                        initial={{ scale: 0.9, y: 20 }}
                        animate={{ scale: 1, y: 0 }}
                        className="bg-gradient-to-br from-red-950 to-black border-2 border-red-500 rounded-xl p-8 max-w-md"
                    >
                        <div className="flex items-center gap-4 mb-6">
                            <div className="p-3 bg-red-500/20 rounded-lg">
                                <AlertTriangle className="w-8 h-8 text-red-400" />
                            </div>
                            <h2 className="text-2xl font-bold text-white uppercase tracking-wider">
                                System Reset
                            </h2>
                        </div>

                        <p className="text-red-300 mb-6">
                            This will perform a complete system reset. All current operations will be terminated
                            and the system will restart. Are you absolutely sure?
                        </p>

                        <div className="flex gap-4">
                            <button
                                onClick={() => setShowConfirmation(false)}
                                className="flex-1 px-4 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-bold uppercase text-sm tracking-wider transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleConfirmReset}
                                className="flex-1 px-4 py-3 bg-red-600 hover:bg-red-500 text-white rounded-lg font-bold uppercase text-sm tracking-wider transition-colors"
                            >
                                Execute Reset
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </>
    );
};
