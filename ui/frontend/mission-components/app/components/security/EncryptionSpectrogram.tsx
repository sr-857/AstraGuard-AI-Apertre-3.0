import * as React from 'react';
import { motion } from 'framer-motion';
import { Shield, ShieldAlert, ShieldCheck, Volume2, VolumeX } from 'lucide-react';
import { useParticleSystem } from '../../hooks/useParticleSystem';
import { useDashboard } from '../../context/DashboardContext';

export const EncryptionSpectrogram: React.FC = () => {
    const { encryptionMetrics } = useDashboard();
    const [audioEnabled, setAudioEnabled] = React.useState(true);
    const audioContextRef = React.useRef<AudioContext | null>(null);
    const lastEntropyRef = React.useRef<number>(0);

    const { canvasRef } = useParticleSystem({
        entropy: encryptionMetrics.entropy,
        isCompromised: encryptionMetrics.isCompromised,
        particleCount: 500,
    });

    // Initialize Web Audio API
    React.useEffect(() => {
        if (typeof window !== 'undefined') {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        return () => {
            audioContextRef.current?.close();
        };
    }, []);

    // Play crystalline clink when entropy reaches 100%
    React.useEffect(() => {
        if (!audioEnabled || !audioContextRef.current) return;

        if (encryptionMetrics.entropy === 100 && lastEntropyRef.current < 100) {
            playCrystallineClink();
        }

        lastEntropyRef.current = encryptionMetrics.entropy;
    }, [encryptionMetrics.entropy, audioEnabled]);

    // Play shatter sound when compromised
    React.useEffect(() => {
        if (!audioEnabled || !audioContextRef.current) return;

        if (encryptionMetrics.isCompromised) {
            playSecurityShatter();
        }
    }, [encryptionMetrics.isCompromised, audioEnabled]);

    const playCrystallineClink = () => {
        const ctx = audioContextRef.current;
        if (!ctx) return;

        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.frequency.setValueAtTime(2000, ctx.currentTime); // High-pitched
        oscillator.frequency.exponentialRampToValueAtTime(3000, ctx.currentTime + 0.1);

        gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);

        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + 0.3);
    };

    const playSecurityShatter = () => {
        const ctx = audioContextRef.current;
        if (!ctx) return;

        // Create chaotic noise burst
        const bufferSize = ctx.sampleRate * 0.5;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }

        const source = ctx.createBufferSource();
        const gainNode = ctx.createGain();
        const filter = ctx.createBiquadFilter();

        source.buffer = buffer;
        source.connect(filter);
        filter.connect(gainNode);
        gainNode.connect(ctx.destination);

        filter.type = 'highpass';
        filter.frequency.setValueAtTime(1000, ctx.currentTime);

        gainNode.gain.setValueAtTime(0.5, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

        source.start(ctx.currentTime);
        source.stop(ctx.currentTime + 0.5);
    };

    const getStatusColor = () => {
        if (encryptionMetrics.isCompromised) return 'text-red-400 border-red-500/50 bg-red-500/10';
        if (encryptionMetrics.entropy >= 90) return 'text-green-400 border-green-500/50 bg-green-500/10';
        if (encryptionMetrics.entropy >= 70) return 'text-cyan-400 border-cyan-500/50 bg-cyan-500/10';
        return 'text-yellow-400 border-yellow-500/50 bg-yellow-500/10';
    };

    const getStatusIcon = () => {
        if (encryptionMetrics.isCompromised) return ShieldAlert;
        if (encryptionMetrics.entropy >= 90) return ShieldCheck;
        return Shield;
    };

    const getStatusText = () => {
        if (encryptionMetrics.isCompromised) return 'COMPROMISED';
        if (encryptionMetrics.entropy === 100) return 'QUANTUM SECURE';
        if (encryptionMetrics.entropy >= 90) return 'SECURE';
        if (encryptionMetrics.entropy >= 70) return 'NOMINAL';
        return 'DEGRADED';
    };

    const StatusIcon = getStatusIcon();

    return (
        <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-black/60 backdrop-blur-xl border border-cyan-500/20 rounded-2xl overflow-hidden shadow-[0_0_30px_rgba(6,182,212,0.2)]"
        >
            {/* Header */}
            <div className="p-4 border-b border-cyan-500/20 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-cyan-500/10 rounded-lg">
                        <Shield className="w-5 h-5 text-cyan-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                            Quantum Encryption
                        </h3>
                        <p className="text-[10px] text-white/40 uppercase tracking-widest">
                            Security Spectrogram
                        </p>
                    </div>
                </div>

                <button
                    onClick={() => setAudioEnabled(!audioEnabled)}
                    className="p-2 hover:bg-white/5 rounded-lg transition-colors"
                >
                    {audioEnabled ? (
                        <Volume2 className="w-4 h-4 text-cyan-400" />
                    ) : (
                        <VolumeX className="w-4 h-4 text-white/40" />
                    )}
                </button>
            </div>

            {/* Particle Canvas */}
            <div className="relative h-64 bg-gradient-to-b from-black/80 to-blue-950/20">
                <canvas
                    ref={canvasRef}
                    className="w-full h-full"
                    style={{ imageRendering: 'crisp-edges' }}
                />

                {/* Overlay Grid */}
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{
                        backgroundImage: `
                            linear-gradient(rgba(6, 182, 212, 0.05) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(6, 182, 212, 0.05) 1px, transparent 1px)
                        `,
                        backgroundSize: '20px 20px',
                    }}
                />
            </div>

            {/* Status Footer */}
            <div className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-white/40 uppercase tracking-wider">Entropy</span>
                        <div className="w-32 h-2 bg-white/10 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                                initial={{ width: 0 }}
                                animate={{ width: `${encryptionMetrics.entropy}%` }}
                                transition={{ duration: 0.5 }}
                            />
                        </div>
                        <span className="text-xs font-mono text-cyan-400 font-bold">
                            {encryptionMetrics.entropy}%
                        </span>
                    </div>
                </div>

                <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${getStatusColor()}`}>
                    <StatusIcon className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-widest">
                        {getStatusText()}
                    </span>
                    {encryptionMetrics.isCompromised && encryptionMetrics.attackType && (
                        <span className="ml-auto text-[10px] text-red-400/60 uppercase">
                            {encryptionMetrics.attackType}
                        </span>
                    )}
                </div>

                {encryptionMetrics.entropy === 100 && !encryptionMetrics.isCompromised && (
                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="text-center py-2"
                    >
                        <p className="text-[10px] text-green-400 uppercase tracking-widest font-bold">
                            ✨ Perfect Encryption Achieved
                        </p>
                    </motion.div>
                )}
            </div>
        </motion.div>
    );
};
