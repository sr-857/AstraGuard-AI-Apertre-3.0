export interface FeatureImportance {
  feature: string;
  importance: number; // 0.0 - 1.0
}

export interface AnalysisResult {
  anomaly_id: string;
  analysis: string;
  recommendation: string;
  confidence: number; // 0.0 - 1.0
  feature_importances?: FeatureImportance[];
  shap_values?: Record<string, number>;
}
