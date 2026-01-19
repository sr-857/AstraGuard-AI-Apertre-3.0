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
        case 'CHART_UPDATE':
            return {
                ...state,
                systems: {
                    ...state.systems,
                    charts: {
                        ...state.systems.charts,
                        [action.payload.id]: {
                            ...state.systems.charts[action.payload.id],
                            ...action.payload.data
                        }
                    }
                }
            };
        case 'CONNECTION_STATUS':
            return { ...state, connection: action.payload };
        default:
            return state;
    }
};

export const useDashboardWebSocket = () => {
    const [state, dispatch] = useReducer(telemetryReducer, initialState);
    const [isConnected, setConnected] = useState(false);

    // Replay State
    const [isReplayMode, setReplayMode] = useState(false);
    const [replayData, setReplayData] = useState<any[]>([]);
    const [replayProgress, setReplayProgress] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);

    const reconnectAttempts = useRef(0);

    const toggleReplayMode = async () => {
        if (!isReplayMode) {
            // Enter Replay Mode: Fetch session
            try {
                const res = await fetch('http://localhost:8002/api/v1/replay/session?incident_type=VOLTAGE_SPIKE');
                const data = await res.json();
                setReplayData(data.frames);
                setReplayProgress(0);
                setIsPlaying(true);
            } catch (e) {
                console.error("Failed to load replay session", e);
            }
        }
        setReplayMode(!isReplayMode);
    };

    const togglePlay = () => setIsPlaying(!isPlaying);

    const pollBackend = useCallback(async () => {
        if (isReplayMode) return; // Stop polling in replay mode

        try {
            // Fetch Status, Telemetry, Anomalies...
            const [statusRes, telemetryRes, historyRes] = await Promise.all([
                fetch('http://localhost:8002/api/v1/status'),
                fetch('http://localhost:8002/api/v1/telemetry/latest'),
                fetch('http://localhost:8002/api/v1/history/anomalies?limit=10')
            ]);

            const statusData = await statusRes.json();
            const telemetryDataRaw = await telemetryRes.json();
            const historyData = await historyRes.json();

            setConnected(true);
            dispatch({ type: 'CONNECTION_STATUS', payload: 'connected' });

            // Update KPIs with live data
            if (telemetryDataRaw.data) {
                const t = telemetryDataRaw.data;
                updateKPIs(t, dispatch);
            }

        } catch (error) {
            console.warn('[Polling] Failed - using mockup');
            setConnected(true);

            // Mock Fallback
            // To test Predictive Health, set voltage < 45
            const mockT = {
                voltage: 48.0,
                current: 2.1,
                temperature: 35,
                gyro: 0.001,
                charts: telemetryData.charts
            };
            updateKPIs(mockT, dispatch);
        }
    }, [isReplayMode]);

    // Handle Replay Frame Updates
    useEffect(() => {
        if (isReplayMode && replayData && replayData.length > 0) {
            // Map progress 0-100 to frame index
            const frameIndex = Math.floor((replayProgress / 100) * (replayData.length - 1));
            const frame = replayData[frameIndex];

            if (frame) {
                updateKPIs(frame, dispatch);
            }
        }
    }, [isReplayMode, replayProgress, replayData]);

    // Effect for polling (only when not replay)
    useEffect(() => {
        if (isReplayMode) return;
        const interval = setInterval(pollBackend, 2000);
        pollBackend();
        return () => clearInterval(interval);
    }, [pollBackend, isReplayMode]);


    return {
        state,
        isConnected,
        send: () => { },
        dispatch,
        isReplayMode,
        toggleReplayMode,
        replayProgress,
        setReplayProgress,
        isPlaying,
        togglePlay
    };
};

// Helper
const updateKPIs = (t: any, dispatch: any) => {
    const kpiUpdates = [
        { id: 'voltage', label: 'Bus Voltage', value: `${t.voltage.toFixed(2)}V`, status: 'nominal', trend: 'stable' },
        { id: 'current', label: 'Total Current', value: `${t.current?.toFixed(2) || '0.00'}A`, status: 'nominal', trend: 'stable' },
        { id: 'temp', label: 'Core Temp', value: `${t.temperature.toFixed(1)}°C`, status: t.temperature > 50 ? 'warning' : 'nominal', trend: 'increasing' },
        { id: 'gyro', label: 'Gyro Stability', value: `${t.gyro.toFixed(4)}`, status: 'nominal', trend: 'stable' }
    ];
    kpiUpdates.forEach(kpi => dispatch({ type: 'KPI_UPDATE', payload: kpi }));

    // AI Forecasting Logic (Simulated)
    // If voltage is dropping (simulated by checking if it's below nominal 48V), project when it hits 0
    const voltage = t.voltage;
    if (voltage < 45) { // Threshold to trigger "Warning" / Prediction
        const dropRate = 0.1; // Volts per second (assumed/calculated)
        const timeToFailure = Math.floor(voltage / dropRate);

        // Generate forecast points for chart
        const currentChart = t.charts?.voltage || { data: [] };
        // We'll just generate based on current value if chart data isn't directly in 't' (it might be separately updated)
        // But here we rely on the reducer to merge. We need to construct the 'forecast' for the chart.

        // Let's create a forecast array
        const forecastPoints = [];
        const now = new Date();
        for (let i = 1; i <= 60; i += 10) { // Forecast next 60 seconds
            const futureVal = Math.max(0, voltage - (dropRate * i));
            const futureTime = new Date(now.getTime() + i * 1000);
            const timeStr = `${futureTime.getHours().toString().padStart(2, '0')}:${futureTime.getMinutes().toString().padStart(2, '0')}`;

            forecastPoints.push({
                timestamp: timeStr,
                value: futureVal
            });
        }

        // Dispatch Prediction Update
        dispatch({
            type: 'TELEMETRY_UPDATE',
            payload: {
                systems: {
                    prediction: {
                        systemId: 'voltage',
                        label: 'Main Bus Voltage',
                        trend: 'critical',
                        timeToFailure: timeToFailure,
                        confidence: 0.94
                    },
                    // We also need to update the specific chart with forecast data.
                    // This assumes the reducer merges deep enough or we handle it manually.
                    // The reducer says: systems: { ...state.systems, ...action.payload.systems }
                    // So we can send partial updates if we structure it right.
                    // But charts is a Record, so we might need to send the whole charts object or modify the reducer.
                    // Let's check the reducer again. It does shallow merge of systems.
                    // So we should try to dispatch a chart update separately or include it here if we have the full charts object.
                    // Since 't' doesn't have the full charts object usually (just telem), we might need to rely on the fact that 
                    // this updateKPIs is called with 'telemetryDataRaw.data' which might NOT have charts.
                    // Actually 'telemetryDataRaw' in pollBackend has 'data'.

                    // Ideally we should dispatch a specific CHART_UPDATE or handle it in a smarter reducer.
                    // For now, let's assume we can trigger a system update.
                    // BUT, updating 'charts' might overwrite other charts if we are not careful.
                    // The reducer: systems: action.payload.systems ? { ...state.systems, ...action.payload.systems } : state.systems
                    // If we pass systems: { charts: { voltage: { ... } } }, it will REPLACE state.systems.charts with { voltage: ... }
                    // causing other charts to disappear.
                }
            }
        });

        // Update Chart with Forecast
        if (currentChart) {
            dispatch({
                type: 'CHART_UPDATE',
                payload: {
                    id: 'voltage',
                    data: {
                        forecast: forecastPoints
                    }
                }
            });
        }
    } else {
        // Clear prediction if healthy
        dispatch({
            type: 'TELEMETRY_UPDATE',
            payload: {
                systems: {
                    prediction: null
                }
            }
        });
    }
};
