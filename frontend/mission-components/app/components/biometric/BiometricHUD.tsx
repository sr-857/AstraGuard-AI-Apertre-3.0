import * as React from 'react';
import { motion } from 'framer-motion';
import { Activity, Brain, Eye, Heart } from 'lucide-react';
import { BiometricData, ReadinessLevel } from '../../types/biometric';

interface BiometricHUDProps {
    biometricData: BiometricData;
}

export const BiometricHUD: React.FC<BiometricHUDProps> = ({ biometricData }) => {
    const getReadinessColor = (level: ReadinessLevel) => {
        switch (level) {
            case ReadinessLevel.OPTIMAL:
                return 'text-cyan-400 border-cyan-500/50';
            case ReadinessLevel.ALERT:
                return 'text-yellow-400 border-yellow-500/50';
            case ReadinessLevel.FATIGUED:
                return 'text-orange-400 border-orange-500/50';
            case ReadinessLevel.CRITICAL:
                return 'text-red-400 border-red-500/50';
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="fixed top-6 left-6 z-50"
        >
            <div className="bg-black/80 backdrop-blur-xl border-2 border-white/10 rounded-xl p-3 min-w-[200px]">
                {/* Readiness Level Header */}
                <div className={`flex items-center gap-2 mb-3 pb-2 border-b ${getReadinessColor(biometricData.readinessLevel)}`}>
                    <Activity className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">{biometricData.readinessLevel}</span>
                    <span className="ml-auto text-xs font-mono">{biometricData.readinessScore}%</span>
                </div>

                {/* Metrics */}
                <div className="space-y-2">
                    {/* Heart Rate */}
                    <div className="flex items-center gap-2">
                        <Heart className="w-3 h-3 text-red-400" />
                        <span className="text-[10px] text-white/60 uppercase tracking-widest">HR</span>
                        <motion.span
                            className="ml-auto text-xs font-mono text-white font-bold"
                            animate={{ scale: [1, 1.1, 1] }}
                            transition={{ duration: 60 / biometricData.heartRate, repeat: Infinity }}
                        >
                            {biometricData.heartRate}
                        </motion.span>
                        <span className="text-[10px] text-white/40">BPM</span>
                    </div>

                    {/* Stress Level */}
                    <div className="flex items-center gap-2">
                        <Brain className="w-3 h-3 text-purple-400" />
                        <span className="text-[10px] text-white/60 uppercase tracking-widest">Stress</span>
                        <div className="ml-auto flex items-center gap-1">
                            <div className="w-16 h-1.5 bg-black/30 rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full bg-gradient-to-r from-cyan-500 via-yellow-500 to-red-500"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${biometricData.stressLevel}%` }}
                                    transition={{ duration: 0.5 }}
                                />
                            </div>
                            <span className="text-xs font-mono text-white/60">{biometricData.stressLevel}%</span>
                        </div>
                    </div>

                    {/* Attention Score */}
                    <div className="flex items-center gap-2">
                        <Eye className="w-3 h-3 text-cyan-400" />
                        <span className="text-[10px] text-white/60 uppercase tracking-widest">Focus</span>
                        <div className="ml-auto flex items-center gap-1">
                            <div className="w-16 h-1.5 bg-black/30 rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full bg-cyan-500"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${biometricData.attentionScore}%` }}
                                    transition={{ duration: 0.5 }}
                                />
                            </div>
                            <span className="text-xs font-mono text-white/60">{biometricData.attentionScore}%</span>
                        </div>
                    </div>
                </div>

                {/* Missed Alerts Warning */}
                {biometricData.missedAlerts > 0 && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="mt-3 pt-2 border-t border-red-500/30"
                    >
                        <p className="text-[10px] text-red-400 font-bold">
                            ⚠️ {biometricData.missedAlerts} Missed Alert{biometricData.missedAlerts !== 1 ? 's' : ''}
                        </p>
                    </motion.div>
                )}
            </div>
        </motion.div>
    );
};
