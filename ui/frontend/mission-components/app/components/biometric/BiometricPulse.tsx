import * as React from 'react';
import { motion } from 'framer-motion';
import { BiometricData, ReadinessLevel } from '../../types/biometric';

interface BiometricPulseProps {
    biometricData: BiometricData;
}

export const BiometricPulse: React.FC<BiometricPulseProps> = ({ biometricData }) => {
    const getPulseColor = (level: ReadinessLevel) => {
        switch (level) {
            case ReadinessLevel.OPTIMAL:
                return 'rgba(34, 211, 238, 0.15)'; // Cyan
            case ReadinessLevel.ALERT:
                return 'rgba(234, 179, 8, 0.2)'; // Yellow
            case ReadinessLevel.FATIGUED:
                return 'rgba(249, 115, 22, 0.25)'; // Orange
            case ReadinessLevel.CRITICAL:
                return 'rgba(239, 68, 68, 0.3)'; // Red
        }
    };

    // Calculate pulse duration based on heart rate (60 BPM = 1s, 120 BPM = 0.5s)
    const pulseDuration = 60 / biometricData.heartRate;

    return (
        <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
            {/* Primary Pulse */}
            <motion.div
                className="absolute inset-0"
                style={{
                    background: `radial-gradient(circle at center, ${getPulseColor(
                        biometricData.readinessLevel
                    )}, transparent 70%)`,
                }}
                animate={{
                    opacity: [0.3, 0.6, 0.3],
                    scale: [1, 1.05, 1],
                }}
                transition={{
                    duration: pulseDuration,
                    repeat: Infinity,
                    ease: 'easeInOut',
                }}
            />

            {/* Secondary Pulse (offset for heartbeat effect) */}
            <motion.div
                className="absolute inset-0"
                style={{
                    background: `radial-gradient(circle at center, ${getPulseColor(
                        biometricData.readinessLevel
                    )}, transparent 60%)`,
                }}
                animate={{
                    opacity: [0.2, 0.4, 0.2],
                    scale: [1, 1.03, 1],
                }}
                transition={{
                    duration: pulseDuration,
                    repeat: Infinity,
                    ease: 'easeInOut',
                    delay: pulseDuration * 0.15, // Slight delay for double-beat effect
                }}
            />

            {/* Stress Indicator - Corner Vignette */}
            {biometricData.stressLevel > 50 && (
                <motion.div
                    className="absolute inset-0"
                    style={{
                        background: `radial-gradient(circle at center, transparent 40%, rgba(239, 68, 68, ${biometricData.stressLevel / 200
                            }) 100%)`,
                    }}
                    animate={{
                        opacity: [0.5, 0.8, 0.5],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />
            )}
        </div>
    );
};
