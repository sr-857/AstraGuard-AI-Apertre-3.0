export interface FederatedLearningConfig {
    nodeId: string;
    learningRate: number;
    batchSize: number;
    epochs: number;
    privacyBudget: number;
    aggregationRounds: number;
    minNodesForAggregation: number;
}
