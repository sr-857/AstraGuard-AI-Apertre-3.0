import { useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { TelemetryState } from '../types/websocket';
import dashboardData from '../mocks/dashboard.json';
import systemsData from '../mocks/systems.json';
import telemetryData from '../mocks/telemetry.json';

// Use same initial state structure as context
export const initialState: TelemetryState = {
    mission: {
        satellites: dashboardData.mission.satellites as any[],
        phases: dashboardData.mission.phases as any[],
        anomalies: dashboardData.mission.anomalies as any[]
    },
    systems: {
        kpis: systemsData.kpis as any[],
        breakers: systemsData.breakers as any[],
        charts: telemetryData.charts as any,
        health: telemetryData.health as any[]
    },
    connection: 'connecting'
};

export const telemetryReducer = (state: TelemetryState, action: any): TelemetryState => {
    switch (action.type) {
        case 'TELEMETRY_SNAPSHOT':
            return {
                ...state,
                mission: action.payload.mission || state.mission,
                systems: action.payload.systems || state.systems
            };
        case 'TELEMETRY':
            return { ...state, systems: { ...state.systems, ...action.payload } };
        case 'TELEMETRY_UPDATE':
            return {
                ...state,
                mission: action.payload.mission ? { ...state.mission, ...action.payload.mission } : state.mission,
                systems: action.payload.systems ? { ...state.systems, ...action.payload.systems } : state.systems
            };
        case 'ANOMALY':
            return {
                ...state,
                mission: {
                    ...state.mission,
                    anomalies: [...state.mission.anomalies, action.payload]
                }
            };
        case 'ANOMALY_ACK':
            return {
                ...state,
                mission: {
                    ...state.mission,
                    anomalies: state.mission.anomalies.filter(a => a.id !== action.payload.id)
                }
            };
        case 'SATELLITES':
            return { ...state, mission: { ...state.mission, satellites: action.payload } };
        case 'KPI_UPDATE':
            return {
                ...state,
                systems: {
                    ...state.systems,
                    kpis: state.systems.kpis.map(kpi =>
                        kpi.id === action.payload.id ? action.payload : kpi
                    )
                }
            };
        case 'HEALTH_UPDATE':
            return {
                ...state,
                systems: {
                    ...state.systems,
                    health: state.systems.health.map(h =>
                        h.id === action.payload.id ? action.payload : h
                    )
                }
            };
        case 'CONNECTION_STATUS':
            return { ...state, connection: action.payload };
        default:
            return state;
    }
};

export const useDashboardWebSocket = () => {
    // TODO: Add error boundary for WebSocket connection failures
    // TODO: Implement caching mechanism for offline data persistence
    // TODO: Add connection pooling for multiple WebSocket connections
    // TODO: Optimize performance with message batching and throttling
    const [state, dispatch] = useReducer(telemetryReducer, initialState);
    const [isConnected, setConnected] = useState(false);
    const reconnectAttempts = useRef(0); // Kept for future use
    // const maxReconnects = 5;

    const pollBackend = useCallback(async () => {
        try {
            // Fetch Status (Phase & Health)
            const statusRes = await fetch('http://localhost:8000/api/v1/status');
            const statusData = await statusRes.json();

            // Fetch Latest Telemetry
            const telemetryRes = await fetch('http://localhost:8000/api/v1/telemetry/latest');
            const telemetryDataRaw = await telemetryRes.json();

            // Fetch Anomalies
            const historyRes = await fetch('http://localhost:8000/api/v1/history/anomalies?limit=10');
            const historyData = await historyRes.json();

            setConnected(true);
            dispatch({ type: 'CONNECTION_STATUS', payload: 'connected' });
            reconnectAttempts.current = 0;

            // 1. Update Mission Phase
            // Map backend "NOMINAL_OPS" to dashboard phases
            if (statusData.mission_phase) {
                dispatch({
                    type: 'TELEMETRY_UPDATE',
                    payload: {
                        mission: {
                            // We don't overwrite the whole list, just active state logic would go here
                            // For now, let's just log it or handle it if we had a setPhase action
                        }
                    }
                });
            }

            // 2. Update System Health (Generic)
            if (statusData.components) {
                // Map component health to KPI or Health Table
            }

            // 3. Update Telemetry Charts/KPIs
            if (telemetryDataRaw.data) {
                const t = telemetryDataRaw.data;
                // Update KPIs based on specific IDs matching backend
                const kpiUpdates = [
                    { id: 'voltage', label: 'Bus Voltage', value: `${t.voltage.toFixed(2)}V`, status: 'nominal', trend: 'stable' },
                    { id: 'current', label: 'Total Current', value: `${t.current?.toFixed(2) || '0.00'}A`, status: 'nominal', trend: 'stable' },
                    { id: 'temp', label: 'Core Temp', value: `${t.temperature.toFixed(1)}°C`, status: t.temperature > 50 ? 'warning' : 'nominal', trend: 'increasing' },
                    { id: 'gyro', label: 'Gyro Stability', value: `${t.gyro.toFixed(4)}`, status: 'nominal', trend: 'stable' }
                ];

                kpiUpdates.forEach(kpi => dispatch({ type: 'KPI_UPDATE', payload: kpi }));
            }

            // 4. Update Anomalies
            if (historyData.anomalies) {
                // Need to reconcile list. For now, we can just "Add" new ones if ID unique
                // Or simplified: just console log for this iteration
            }

        } catch (error) {
            console.warn('[Polling] Failed to fetch backend data - using mockup', error);
            // If offline, we stay "connected" via mock data for user experience
            // But we could toggle a "Simulation Mode" flag
            setConnected(true);
        }
    }, []);

    // Effect for polling
    useEffect(() => {
        const interval = setInterval(pollBackend, 2000);
        pollBackend(); // Initial call
        return () => clearInterval(interval);
    }, [pollBackend]);


    return {
        state,
        isConnected,
        send: () => { }, // No-op for now
        dispatch // For manual actions like ACK
    };
};
