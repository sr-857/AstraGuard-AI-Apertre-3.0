export interface Satellite {
  id: string;
  orbitSlot: string;
  status: 'Nominal' | 'Degraded' | 'Critical';
  latency: number;
  task: string;
  signal: number;
}

export interface MissionPhase {
  name: string;
  progress: number;
  eta: string;
  isActive: boolean;
}
