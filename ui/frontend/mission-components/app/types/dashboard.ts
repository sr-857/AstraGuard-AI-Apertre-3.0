export type SatelliteStatus = 'Nominal' | 'Degraded' | 'Critical';

export interface Satellite {
  id: string;
  name: string;
  status: SatelliteStatus;
  orbit: string;
  orbitSlot: string;
  latency: number;
  task: string;
  signalStrength: number;
}

export interface RemediationStep {
  id: string;
  command: string;
  description: string;
  status: 'pending' | 'executing' | 'completed' | 'failed';
}

export interface RemediationScript {
  id: string;
  anomalyId: string;
  steps: RemediationStep[];
  status: 'proposed' | 'authorized' | 'executing' | 'completed';
  createdAt: string;
}

export interface MissionPhase {
  name: string;
  status: 'complete' | 'active' | 'pending';
  progress: number;
  eta?: string;
  isActive: boolean;
}

export interface AnomalyEvent {
  id: string;
  message?: string;
  severity: 'Critical' | 'Warning' | 'Info';
  timestamp: string;
  satellite: string;
  metric: string;
  value: string;
  acknowledged: boolean;
  aiRCA?: string;
  analysisStatus?: 'pending' | 'completed' | 'failed';
}

export interface GroundStation {
  id: string;
  name: string;
  lat: number;
  lng: number;
  weather: 'Clear' | 'Rain' | 'Storm' | 'Clouds';
  signalQuality: number; // 0 to 1
  connectedSatelliteId?: string;
}

export interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string; // Lucide icon name or emoji
  unlockedAt?: string;
  isNew?: boolean;
  category: 'Tactical' | 'Safety' | 'Historical' | 'Chaos';
}

export interface HistoricalAnomaly {
  lat: number;
  lng: number;
  intensity: number; // 0-1 based on frequency
  count: number;
  type: string;
}

export interface AICognitiveState {
  load: number; // 0-100
  synapticThroughput: number; // nodes/sec
  attentionFocus: string; // current subsystem being analyzed
  confidence: number; // 0-1
  activeNeurons: number;
}

export interface MissionState {
  name: string;
  phase: string;
  status: 'Nominal' | 'Degraded' | 'Critical';
  updated: string;
  anomalyCount: number;
  satellites: Satellite[];
  phases: MissionPhase[];
  anomalies: AnomalyEvent[];
  groundStations: GroundStation[];
  aiHealth: AICognitiveState;
}
