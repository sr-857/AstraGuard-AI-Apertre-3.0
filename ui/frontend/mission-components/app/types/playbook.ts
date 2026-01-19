export enum PlaybookStatus {
    ACTIVE = 'ACTIVE',
    COMPLETED = 'COMPLETED',
    DISMISSED = 'DISMISSED',
}

export enum StepStatus {
    PENDING = 'PENDING',
    IN_PROGRESS = 'IN_PROGRESS',
    COMPLETED = 'COMPLETED',
    FAILED = 'FAILED',
}

export interface RemediationStep {
    id: string;
    description: string;
    command: string;
    targetPanel?: string; // ID of panel to highlight (e.g., 'battery-panel', 'power-systems')
    estimatedDuration?: number; // Seconds
    status: StepStatus;
    errorMessage?: string;
}

export interface IncidentPlaybook {
    id: string;
    anomalyId: string;
    title: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    steps: RemediationStep[];
    status: PlaybookStatus;
    createdAt: string;
    completedAt?: string;
}

export interface CommandExecutionResult {
    success: boolean;
    message?: string;
    data?: any;
}
