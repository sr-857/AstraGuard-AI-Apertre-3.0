export interface EncryptionMetrics {
    entropy: number; // 0-100, measures randomness/unpredictability
    strength: number; // 0-100, overall encryption strength
    isCompromised: boolean;
    lastAttackTime?: string;
    attackType?: 'MITM' | 'REPLAY' | 'BRUTE_FORCE' | null;
}

export type SecurityEvent = {
    id: string;
    type: 'ATTACK_DETECTED' | 'ENCRYPTION_RESTORED' | 'ENTROPY_CRITICAL';
    timestamp: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    description: string;
};

export interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    life: number;
    maxLife: number;
    hue: number;
    size: number;
}
