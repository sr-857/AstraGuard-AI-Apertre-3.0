import { AnomalyEvent } from '../app/types/dashboard';

export class AIService {
    private static instance: AIService;

    private rcaDatabase: Record<string, string> = {
        'CPU': 'High computational load detected in the propulsion subsystem. Likely caused by a recursive loop in the guidance logic or external sensor noise.',
        'Memory': 'Memory leak detected in the telemetry buffer. Historical data suggests a race condition during burst transmission phases.',
        'Signal': 'Signal degradation consistent with solar flare activity in Sector 7-G. Recommend re-orienting the high-gain antenna.',
        'Latency': 'Communication delay spike observed due to orbital occlusion by lunar body. Automatic relay hand-off is pending.',
        'Default': 'Anomalous pattern detected in subsystem telemetry. AI analysis suggests a synchronization mismatch between the primary and redundant logic controllers.'
    };

    static getInstance() {
        if (!this.instance) {
            this.instance = new AIService();
        }
        return this.instance;
    }

    async analyzeAnomaly(anomaly: AnomalyEvent): Promise<string> {
        // Simulate network delay for "AI crunching"
        await new Promise(resolve => setTimeout(resolve, 1500));

        const key = Object.keys(this.rcaDatabase).find(k =>
            anomaly.metric?.toLowerCase().includes(k.toLowerCase()) ||
            anomaly.message?.toLowerCase().includes(k.toLowerCase())
        );

        return this.rcaDatabase[key || 'Default'];
    }

    async getCopilotResponse(query: string, context: any): Promise<string> {
        await new Promise(resolve => setTimeout(resolve, 800));

        const q = query.toLowerCase();
        if (q.includes('risk') || q.includes('satellites')) {
            const risky = context.mission.satellites.filter((s: any) => s.status !== 'Nominal').length;
            return `I have analyzed the fleet. ${risky > 0 ? `${risky} satellites are currently showing signs of degradation.` : 'All satellites are currently nominal.'} I recommend keeping an eye on the ${context.mission.satellites[0].name} for potential thermal drift.`;
        }

        if (q.includes('anomaly') || q.includes('severity')) {
            const high = context.mission.anomalies.filter((a: any) => a.severity === 'Critical').length;
            return `There are currently ${high} critical anomalies requiring immediate attention. The most recent one is at ${context.mission.anomalies[0]?.timestamp}.`;
        }

        return "I am standardizing your request against our defense protocols. Please specify if you want an update on fleet status, anomaly reports, or system health.";
    }
}
