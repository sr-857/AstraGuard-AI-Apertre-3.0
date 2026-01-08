import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { BiometricData } from '../../types/biometric';

interface AutoPilotProposalProps {
    biometricData: BiometricData;
    onEnable: () => void;
    onDismiss: () => void;
}

export const AutoPilotProposal: React.FC<AutoPilotProposalProps> = ({
    biometricData,
    onEnable,
    onDismiss,
}) => {
    if (biometricData.readinessScore >= 60) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[110] flex items-center justify-center p-6"
            >
                <motion.div
                    initial={{ scale: 0.9, y: 20 }}
                    animate={{ scale: 1, y: 0 }}
                    className="bg-gradient-to-br from-gray-900 to-black border-2 border-orange-500/50 rounded-xl max-w-lg w-full overflow-hidden"
                >
                    {/* Header */}
                    <div className="p-6 border-b border-orange-500/30 bg-orange-500/10">
                        <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <div className="p-3 bg-orange-500/20 rounded-lg">
                                    <Bot className="w-6 h-6 text-orange-400" />
                                </div>
                                <div>
                                    <h2 className="text-xl font-bold text-white uppercase tracking-wider">
                                        Auto-Pilot Recommended
                                    </h2>
                                    <p className="text-sm text-orange-400/80">Operator Fatigue Detected</p>
                                </div>
                            </div>
                            <button
                                onClick={onDismiss}
                                className="p-1 hover:bg-white/10 rounded transition-colors"
                            >
                                <X className="w-5 h-5 text-white/60" />
                            </button>
                        </div>

                        {/* Warning */}
                        <div className="flex items-start gap-2 p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                            <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-white/90">
                                Your readiness score is <span className="font-bold text-orange-400">{biometricData.readinessScore}%</span>.
                                AI assistance is recommended for mission-critical operations.
                            </p>
                        </div>
                    </div>

                    {/* Metrics */}
                    <div className="p-6 space-y-4">
                        <div className="grid grid-cols-3 gap-3">
                            <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                <p className="text-xs text-white/60 uppercase tracking-widest mb-1">Heart Rate</p>
                                <p className="text-lg font-bold text-white">{biometricData.heartRate}</p>
                                <p className="text-xs text-white/40">BPM</p>
                            </div>
                            <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                <p className="text-xs text-white/60 uppercase tracking-widest mb-1">Stress</p>
                                <p className="text-lg font-bold text-orange-400">{biometricData.stressLevel}%</p>
                            </div>
                            <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                <p className="text-xs text-white/60 uppercase tracking-widest mb-1">Focus</p>
                                <p className="text-lg font-bold text-red-400">{biometricData.attentionScore}%</p>
                            </div>
                        </div>

                        {/* Auto-Pilot Features */}
                        <div>
                            <p className="text-sm font-bold text-white mb-3">Auto-Pilot will handle:</p>
                            <div className="space-y-2">
                                {[
                                    'Anomaly detection and prioritization',
                                    'Routine system health monitoring',
                                    'Non-critical command execution',
                                    'Alert aggregation and filtering',
                                ].map((feature, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                                        <span className="text-sm text-white/80">{feature}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="p-6 border-t border-white/10 bg-white/5 flex gap-3">
                        <button
                            onClick={onDismiss}
                            className="flex-1 px-4 py-3 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-bold uppercase tracking-wider rounded-lg transition-colors"
                        >
                            I'll Continue
                        </button>
                        <button
                            onClick={onEnable}
                            className="flex-1 px-4 py-3 bg-cyan-500 hover:bg-cyan-400 text-black font-bold uppercase tracking-wider rounded-lg transition-colors"
                        >
                            Enable Auto-Pilot
                        </button>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
};
