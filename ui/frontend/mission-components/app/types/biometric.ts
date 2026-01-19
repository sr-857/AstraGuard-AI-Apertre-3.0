export enum ReadinessLevel {
    OPTIMAL = 'OPTIMAL',       // 80-100: Fully alert and ready
    ALERT = 'ALERT',           // 60-79: Slightly elevated stress
    FATIGUED = 'FATIGUED',     // 40-59: Showing signs of fatigue
    CRITICAL = 'CRITICAL',     // 0-39: Dangerously fatigued
}

export interface BiometricData {
    heartRate: number;          // BPM (60-120)
    stressLevel: number;        // 0-100
    attentionScore: number;     // 0-100
    readinessScore: number;     // 0-100 (composite score)
    readinessLevel: ReadinessLevel;
    missedAlerts: number;
    lastAlertTime?: number;     // Timestamp of last alert
}

export interface AttentionMetrics {
    totalAlerts: number;
    acknowledgedAlerts: number;
    missedAlerts: number;
    averageResponseTime: number; // Milliseconds
    isHighContrastMode: boolean;
}
