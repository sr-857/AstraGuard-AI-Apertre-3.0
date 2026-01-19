'use client';

import { createContext, useContext, ReactNode, useState, useEffect } from 'react';
import { TelemetryState, WSMessage } from '../types/websocket';
import { useDashboardWebSocket } from '../hooks/useDashboardWebSocket';
import { useStateBuffer } from '../hooks/useStateBuffer';
import { RemediationScript, RemediationStep, AICognitiveState, HistoricalAnomaly, Achievement } from '../types/dashboard';
import { EncryptionMetrics } from '../types/security';
import { SpaceWeatherData } from '../types/spaceWeather';
import { useSpaceWeather } from '../hooks/useSpaceWeather';
import { DebrisObject, ProximityLevel } from '../types/debris';
import { useDebrisTracking } from '../hooks/useDebrisTracking';
import { IncidentPlaybook, StepStatus } from '../types/playbook';
import { BiometricData } from '../types/biometric';
import { useBiometricTracking } from '../hooks/useBiometricTracking';
import { GroundStation } from '../types/groundStation';
import { useGroundStations } from '../hooks/useGroundStations';
import { DragPhysics } from '../types/physics';
import { useAtmosphericDrag } from '../hooks/useAtmosphericDrag';

export interface Annotation {
    id: string;
    targetId: string; // ID of anomaly or metric
    text: string;
    author: string;
    timestamp: string;
}

export interface Operator {
    id: string;
    name: string;
    avatar: string;
    activePanel: string;
}

interface ContextValue {
    state: TelemetryState;
    isConnected: boolean;
    send: (msg: WSMessage) => void;
    dispatch: any;
    isReplayMode: boolean;
    toggleReplayMode: () => void;
    replayProgress: number;
    setReplayProgress: (p: any) => void;
    isPlaying: boolean;
    togglePlay: () => void;
    isBattleMode: boolean;
    setBattleMode: (active: boolean) => void;
    // Temporal Replay (DVR)
    isReplaying: boolean;
    replayTimestamp: number | null;
    enterReplayMode: () => void;
    exitReplayMode: () => void;
    seekToTimestamp: (timestamp: number) => void;
    getReplayTimeRange: () => { start: number; end: number } | null;
    replayPlaybackSpeed: number;
    setReplayPlaybackSpeed: (speed: number) => void;
    // Collaboration
    annotations: Annotation[];
    addAnnotation: (note: Omit<Annotation, 'id' | 'timestamp'>) => void;
    removeAnnotation: (id: string) => void;
    presence: Operator[];
    // Remediation
    activeRemediation: RemediationScript | null;
    proposeRemediation: (anomalyId: string) => void;
    authorizeRemediation: (id: string) => void;
    cancelRemediation: () => void;
    // Ground Stations
    groundStations: GroundStation[];
    // AI Health
    aiHealth: AICognitiveState;
    // Historical Intelligence
    historicalAnomalies: HistoricalAnomaly[];
    // Gamification
    achievements: Achievement[];
    unlockAchievement: (id: string) => void;
    registerChaosRun: () => void;
    chaosCount: number;
    // Encryption Security
    encryptionMetrics: EncryptionMetrics;
    updateEncryptionMetrics: (metrics: Partial<EncryptionMetrics>) => void;
    // Space Weather
    spaceWeather: SpaceWeatherData;
    distortionIntensity: number;
    isGeomagneticStorm: boolean;
    // System Reset
    executeSystemReset: () => void;
    isResetInProgress: boolean;
    // Debris Tracking
    debrisObjects: DebrisObject[];
    closestDebris: DebrisObject | null;
    proximityLevel: ProximityLevel;
    criticalDebrisCount: number;
    // Incident Playbook
    activePlaybook: IncidentPlaybook | null;
    setActivePlaybook: (playbook: IncidentPlaybook | null) => void;
    // Biometric Tracking
    biometricData: BiometricData;
    incrementMissedAlerts: () => void;
    resetMissedAlerts: () => void;
    isAutoPilotActive: boolean;
    enableAutoPilot: () => void;
    disableAutoPilot: () => void;
    // Ground Stations
    groundStations: GroundStation[];
    activeStation: GroundStation | null;
    switchStation: (stationId: string) => void;
    // Atmospheric Drag
    dragPhysics: DragPhysics;
    executeReboost: () => void;
}

const DashboardContext = createContext<ContextValue | undefined>(undefined);

export const DashboardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const ws = useDashboardWebSocket();
    const stateBuffer = useStateBuffer();
    const { spaceWeather, distortionIntensity, isGeomagneticStorm } = useSpaceWeather();
    const { debrisObjects, closestDebris, proximityLevel, criticalDebrisCount } = useDebrisTracking();
    const [isBattleMode, setBattleMode] = useState(false);
    const [annotations, setAnnotations] = useState<Annotation[]>([]);
    const [presence] = useState<Operator[]>([
        { id: '1', name: 'SIGMA', avatar: 'Σ', activePanel: 'Mission Control' },
        { id: '2', name: 'ALPHA', avatar: 'A', activePanel: 'Systems' },
        { id: '3', name: 'KAPPA', avatar: 'K', activePanel: 'Chaos Engine' },
    ]);
    const [activeRemediation, setActiveRemediation] = useState<RemediationScript | null>(null);

    /* 
       Legacy groundStations state removed.
       Now using useGroundStations hook below.
    */

    const [aiHealth, setAiHealth] = useState<AICognitiveState>({
        load: 12,
        synapticThroughput: 1450,
        attentionFocus: 'Orbit Optimization',
        confidence: 0.99,
        activeNeurons: 4200
    });

    const [historicalAnomalies] = useState<HistoricalAnomaly[]>([
        // South Atlantic Anomaly (Radiation Zone)
        { lat: -30, lng: -45, intensity: 0.9, count: 124, type: 'Radiation' },
        { lat: -28, lng: -47, intensity: 0.7, count: 89, type: 'Radiation' },
        { lat: -32, lng: -43, intensity: 0.85, count: 112, type: 'Radiation' },
        // High Latitude Signal Drop (Ionospheric Interference)
        { lat: 70, lng: 20, intensity: 0.6, count: 45, type: 'Signal Loss' },
        { lat: 72, lng: 15, intensity: 0.5, count: 32, type: 'Signal Loss' },
        // Equatorial Debris Belt
        { lat: 0, lng: 120, intensity: 0.75, count: 67, type: 'Debris Potential' },
        { lat: 2, lng: 118, intensity: 0.4, count: 21, type: 'Debris Potential' },
    ]);

    const [achievements, setAchievements] = useState<Achievement[]>([
        { id: 'chaos-king', title: 'The Chaos King', description: 'Initiate 3 tactical stress tests.', icon: 'Zap', category: 'Chaos' },
        { id: 'first-responder', title: 'First Responder', description: 'Acknowledge an anomaly.', icon: 'ShieldAlert', category: 'Tactical' },
        { id: 'historian', title: 'The Historian', description: 'Analyze historical hotspots.', icon: 'Library', category: 'Historical' },
        { id: 'safety-first', title: 'Safety First', description: 'Execute a successful remediation.', icon: 'CheckCircle2', category: 'Safety' },
    ]);

    const [chaosCount, setChaosCount] = useState(0);

    // Temporal Replay State
    const [isReplaying, setIsReplaying] = useState(false);
    const [replayTimestamp, setReplayTimestamp] = useState<number | null>(null);
    const [replayPlaybackSpeed, setReplayPlaybackSpeed] = useState(1);
    const [replayState, setReplayState] = useState<TelemetryState | null>(null);

    // Encryption Security State
    const [encryptionMetrics, setEncryptionMetrics] = useState<EncryptionMetrics>({
        entropy: 95,
        strength: 98,
        isCompromised: false,
        attackType: null,
    });

    // System Reset State
    const [isResetInProgress, setIsResetInProgress] = useState(false);

    const executeSystemReset = () => {
        setIsResetInProgress(true);
        // Simulate system reset (in production, this would call backend API)
        setTimeout(() => {
            console.log('System reset executed');
            setIsResetInProgress(false);
            // Reset all state to defaults
            window.location.reload();
        }, 2000);
    };

    // Incident Playbook State
    const [activePlaybook, setActivePlaybook] = useState<IncidentPlaybook | null>(null);

    // Biometric Tracking State
    const { biometricData, incrementMissedAlerts, resetMissedAlerts } = useBiometricTracking();
    const [isAutoPilotActive, setIsAutoPilotActive] = useState(false);

    const enableAutoPilot = () => {
        setIsAutoPilotActive(true);
        console.log('Auto-pilot enabled');
    };

    const disableAutoPilot = () => {
        setIsAutoPilotActive(false);
        console.log('Auto-pilot disabled');
    };

    // Ground Station State
    const { groundStations, activeStation, switchStation } = useGroundStations();

    // Atmospheric Drag State
    const { physics: dragPhysics, executeReboost } = useAtmosphericDrag();

    const unlockAchievement = (id: string) => {
        setAchievements(prev => {
            const ach = prev.find(a => a.id === id);
            if (ach && ach.unlockedAt) return prev; // Already unlocked

            return prev.map(a =>
                a.id === id ? { ...a, unlockedAt: new Date().toISOString(), isNew: true } : a
            );
        });

        // Clear "isNew" after a delay
        setTimeout(() => {
            setAchievements(prev => prev.map(a =>
                a.id === id ? { ...a, isNew: false } : a
            ));
        }, 5000);
    };

    const registerChaosRun = () => {
        setChaosCount(prev => {
            const newCount = prev + 1;
            if (newCount >= 3) unlockAchievement('chaos-king');
            return newCount;
        });
    };

    // Capture live telemetry into state buffer
    useEffect(() => {
        if (!isReplaying && ws.state) {
            stateBuffer.addSnapshot(ws.state);
        }
    }, [ws.state, isReplaying, stateBuffer]);

    // Temporal Replay Controls
    const enterReplayMode = () => {
        const timeRange = stateBuffer.getTimeRange();
        if (timeRange) {
            setIsReplaying(true);
            setReplayTimestamp(timeRange.end); // Start at most recent
            const snapshot = stateBuffer.getSnapshotAtTime(timeRange.end);
            if (snapshot) setReplayState(snapshot);
        }
    };

    const exitReplayMode = () => {
        setIsReplaying(false);
        setReplayTimestamp(null);
        setReplayState(null);
    };

    const seekToTimestamp = (timestamp: number) => {
        if (!isReplaying) return;
        setReplayTimestamp(timestamp);
        const snapshot = stateBuffer.getSnapshotAtTime(timestamp);
        if (snapshot) setReplayState(snapshot);
    };

    const getReplayTimeRange = () => {
        return stateBuffer.getTimeRange();
    };

    // Encryption Metrics Management
    const updateEncryptionMetrics = (metrics: Partial<EncryptionMetrics>) => {
        setEncryptionMetrics(prev => ({ ...prev, ...metrics }));
    };

    // Simulate encryption entropy fluctuations
    useEffect(() => {
        const interval = setInterval(() => {
            setEncryptionMetrics(prev => {
                // Random chance of attack (5%)
                if (Math.random() < 0.05 && !prev.isCompromised) {
                    const attacks: Array<'MITM' | 'REPLAY' | 'BRUTE_FORCE'> = ['MITM', 'REPLAY', 'BRUTE_FORCE'];
                    return {
                        ...prev,
                        entropy: Math.max(0, prev.entropy - 50),
                        isCompromised: true,
                        attackType: attacks[Math.floor(Math.random() * attacks.length)],
                        lastAttackTime: new Date().toISOString(),
                    };
                }

                // Recovery from compromise
                if (prev.isCompromised && Math.random() < 0.3) {
                    return {
                        ...prev,
                        entropy: 100,
                        isCompromised: false,
                        attackType: null,
                    };
                }

                // Normal entropy fluctuation
                if (!prev.isCompromised) {
                    const change = (Math.random() - 0.5) * 10;
                    return {
                        ...prev,
                        entropy: Math.max(70, Math.min(100, prev.entropy + change)),
                        strength: Math.max(80, Math.min(100, prev.strength + (Math.random() - 0.5) * 5)),
                    };
                }

                return prev;
            });
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    // Simulate AI Cognitive Fluctuations
    useEffect(() => {
        const interval = setInterval(() => {
            setAiHealth((prev: AICognitiveState) => ({
                ...prev,
                load: Math.max(10, Math.min(95, prev.load + (Math.random() - 0.5) * 5)),
                synapticThroughput: 1400 + Math.floor(Math.random() * 200),
                confidence: 0.95 + Math.random() * 0.05
            }));
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    // Add Annotation
    const addAnnotation = (note: Omit<Annotation, 'id' | 'timestamp'>) => {
        const newNote: Annotation = {
            ...note,
            id: Math.random().toString(36).substr(2, 9),
            timestamp: new Date().toLocaleTimeString(),
        };
        setAnnotations(prev => [newNote, ...prev]);
    };

    // Remove Annotation
    const removeAnnotation = (id: string) => {
        setAnnotations(prev => prev.filter(a => a.id !== id));
    };

    // Propose Remediation (Mock logic)
    const proposeRemediation = (anomalyId: string) => {
        const steps: RemediationStep[] = [
            { id: 's1', command: 'REBOOT_TRANSCEIVER_01', description: 'Hard reset on signal transceiver primary loop', status: 'pending' },
            { id: 's2', command: 'RECALIBRATE_PHASE_ARRAY', description: 'Adjusting phase array to ±0.04° alignment', status: 'pending' },
            { id: 's3', command: 'CLEAR_CACHE_MCR', description: 'Clearing local MCR mission persistent cache', status: 'pending' }
        ];

        setActiveRemediation({
            id: Math.random().toString(36).substr(2, 9),
            anomalyId,
            steps,
            status: 'proposed',
            createdAt: new Date().toLocaleTimeString()
        });
    };

    // Authorize Remediation
    const authorizeRemediation = (id: string) => {
        if (!activeRemediation || activeRemediation.id !== id) return;

        setActiveRemediation(prev => prev ? { ...prev, status: 'authorized' } : null);

        // Mock execution sequence
        setTimeout(() => {
            setActiveRemediation(prev => {
                if (!prev) return null;
                const newSteps = [...prev.steps];
                newSteps[0].status = 'executing';
                return { ...prev, status: 'executing', steps: newSteps };
            });
        }, 1000);

        setTimeout(() => {
            setActiveRemediation(prev => {
                if (!prev) return null;
                const newSteps = [...prev.steps];
                newSteps[0].status = 'completed';
                newSteps[1].status = 'executing';
                return { ...prev, steps: newSteps };
            });
        }, 3000);

        setTimeout(() => {
            setActiveRemediation(prev => {
                if (!prev) return null;
                const newSteps = [...prev.steps];
                newSteps[1].status = 'completed';
                newSteps[2].status = 'completed';
                return { ...prev, status: 'completed', steps: newSteps };
            });
        }, 6000);
    };

    const cancelRemediation = () => {
        setActiveRemediation(null);
    };

    // Auto-trigger Battle Mode on Critical Anomalies
    useEffect(() => {
        if (ws.state.mission?.anomalies) {
            const hasCritical = ws.state.mission.anomalies.some((a: any) => a.severity === 'Critical');
            if (hasCritical && !isBattleMode) {
                setBattleMode(true);
            }
        }
    }, [ws.state.mission?.anomalies, isBattleMode]);

    // Use replay state if in replay mode, otherwise use live state
    const effectiveState = isReplaying && replayState ? replayState : ws.state;

    const value = {
        ...ws,
        state: effectiveState,
        isBattleMode,
        setBattleMode,
        // Temporal Replay
        isReplaying,
        replayTimestamp,
        enterReplayMode,
        exitReplayMode,
        seekToTimestamp,
        getReplayTimeRange,
        replayPlaybackSpeed,
        setReplayPlaybackSpeed,
        annotations,
        addAnnotation,
        removeAnnotation,
        presence,
        activeRemediation,
        proposeRemediation,
        authorizeRemediation,
        cancelRemediation,
        groundStations,
        aiHealth,
        historicalAnomalies,
        achievements,
        unlockAchievement,
        registerChaosRun,
        chaosCount,
        encryptionMetrics,
        updateEncryptionMetrics,
        spaceWeather,
        distortionIntensity,
        isGeomagneticStorm,
        executeSystemReset,
        isResetInProgress,
        debrisObjects,
        closestDebris,
        proximityLevel,
        criticalDebrisCount,
        activePlaybook,
        setActivePlaybook,
        biometricData,
        incrementMissedAlerts,
        resetMissedAlerts,
        isAutoPilotActive,
        enableAutoPilot,
        disableAutoPilot,
        groundStations,
        activeStation,
        switchStation,
        dragPhysics,
        executeReboost,
    };

    return (
        <DashboardContext.Provider value={value}>
            {children}
        </DashboardContext.Provider>
    );
};

export const useDashboard = () => {
    const context = useContext(DashboardContext);
    if (!context) throw new Error('useDashboard must be used within DashboardProvider');
    return context;
};
