import { useState, useEffect, useCallback } from 'react';
import { BiometricData, ReadinessLevel } from '../types/biometric';

interface UseBiometricTrackingReturn {
    biometricData: BiometricData;
    incrementMissedAlerts: () => void;
    resetMissedAlerts: () => void;
}

const getReadinessLevel = (score: number): ReadinessLevel => {
    if (score >= 80) return ReadinessLevel.OPTIMAL;
    if (score >= 60) return ReadinessLevel.ALERT;
    if (score >= 40) return ReadinessLevel.FATIGUED;
    return ReadinessLevel.CRITICAL;
};

export const useBiometricTracking = (): UseBiometricTrackingReturn => {
    const [biometricData, setBiometricData] = useState<BiometricData>({
        heartRate: 72,
        stressLevel: 25,
        attentionScore: 95,
        readinessScore: 90,
        readinessLevel: ReadinessLevel.OPTIMAL,
        missedAlerts: 0,
    });

    const incrementMissedAlerts = useCallback(() => {
        setBiometricData((prev) => {
            const newMissedAlerts = prev.missedAlerts + 1;
            const attentionPenalty = newMissedAlerts * 15; // -15 per missed alert
            const newAttentionScore = Math.max(0, 95 - attentionPenalty);
            const newStressLevel = Math.min(100, prev.stressLevel + 10);
            const newReadinessScore = Math.max(0, (newAttentionScore + (100 - newStressLevel)) / 2);

            return {
                ...prev,
                missedAlerts: newMissedAlerts,
                attentionScore: newAttentionScore,
                stressLevel: newStressLevel,
                readinessScore: newReadinessScore,
                readinessLevel: getReadinessLevel(newReadinessScore),
                lastAlertTime: Date.now(),
            };
        });
    }, []);

    const resetMissedAlerts = useCallback(() => {
        setBiometricData((prev) => ({
            ...prev,
            missedAlerts: 0,
            attentionScore: 95,
            stressLevel: 25,
            readinessScore: 90,
            readinessLevel: ReadinessLevel.OPTIMAL,
        }));
    }, []);

    // Simulate biometric fluctuations
    useEffect(() => {
        const interval = setInterval(() => {
            setBiometricData((prev) => {
                // Natural heart rate variation (±2 BPM)
                const heartRateVariation = (Math.random() - 0.5) * 4;
                const baseHeartRate = 72 + (prev.stressLevel / 100) * 20; // Stress increases HR
                const newHeartRate = Math.max(60, Math.min(120, baseHeartRate + heartRateVariation));

                // Stress level gradually decreases if no missed alerts
                const stressDecay = prev.missedAlerts === 0 ? -0.5 : 0;
                const newStressLevel = Math.max(0, Math.min(100, prev.stressLevel + stressDecay));

                // Attention score gradually recovers
                const attentionRecovery = prev.missedAlerts === 0 ? 0.5 : 0;
                const newAttentionScore = Math.min(95, prev.attentionScore + attentionRecovery);

                // Recalculate readiness score
                const newReadinessScore = (newAttentionScore + (100 - newStressLevel)) / 2;

                return {
                    ...prev,
                    heartRate: Math.round(newHeartRate),
                    stressLevel: Math.round(newStressLevel),
                    attentionScore: Math.round(newAttentionScore),
                    readinessScore: Math.round(newReadinessScore),
                    readinessLevel: getReadinessLevel(newReadinessScore),
                };
            });
        }, 1000); // Update every second

        return () => clearInterval(interval);
    }, []);

    return {
        biometricData,
        incrementMissedAlerts,
        resetMissedAlerts,
    };
};
