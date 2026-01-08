import { Satellite, MissionPhase, AnomalyEvent } from './dashboard';
import { KPI, BreakerState } from './systems';
import { ChartSeries, HealthRow } from './telemetry';

export interface WSMessage {
    type: 'telemetry' | 'anomaly' | 'kpi' | 'health' | 'telemetry_snapshot' | 'anomaly_ack' | 'connection_status';
    payload: any;
    timestamp: string;
}

export interface TelemetryState {
    mission: {
        satellites: Satellite[];
        phases: MissionPhase[];
        anomalies: AnomalyEvent[];
    };
    systems: {
        kpis: KPI[];
        breakers: BreakerState[];
        charts: Record<string, ChartSeries>;
        health: HealthRow[];
        prediction?: {
            systemId: string;
            label: string;
            trend: 'stable' | 'increasing' | 'decreasing' | 'critical';
            timeToFailure?: number;
            confidence: number;
        };
    };
    connection: 'connected' | 'connecting' | 'disconnected';
}
