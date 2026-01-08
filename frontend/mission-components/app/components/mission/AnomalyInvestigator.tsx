import React, { useState, useEffect } from 'react';
import { AnomalyEvent } from '../../types/dashboard';
import { AnalysisResult, FeatureImportance } from '../../types/analysis';

interface Props {
    anomaly: AnomalyEvent;
    onClose: () => void;
}

export const AnomalyInvestigator: React.FC<Props> = ({ anomaly, onClose }) => {
    const [loading, setLoading] = useState(true);
    const [result, setResult] = useState<AnalysisResult | null>(null);

    // Simple deterministic mock generator for explainability when analysis service is unavailable
    const generateMockAnalysis = (an: AnomalyEvent): AnalysisResult => {
        const baseFeatures = ['signal_strength', 'temperature', 'battery', 'latency', 'tx_rate', 'rx_rate'];
        // Deterministically pick features based on metric string
        const seed = an.metric.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
        const rand = (n: number) => ((seed * 9301 + 49297 + n) % 233280) / 233280;
        const feature_importances: FeatureImportance[] = baseFeatures
            .map((f, i) => ({ feature: f, importance: Math.abs(Math.round((rand(i) * (i + 1)) * 100) / 100) }))
            .sort((a, b) => b.importance - a.importance)
            .slice(0, 5);
        const total = feature_importances.reduce((s, x) => s + x.importance, 0) || 1;
        feature_importances.forEach((f) => (f.importance = f.importance / total));

        return {
            anomaly_id: an.id,
            analysis: `Mock root-cause analysis for ${an.metric}: most likely caused by sensor drift and environmental factors.`,
            recommendation: `Suggested actions:\n1) Verify sensor calibration.\n2) Check recent command activity.\n3) Monitor for 30 minutes before automated recovery.`,
            confidence: Math.min(0.95, 0.6 + (seed % 40) / 100),
            feature_importances,
            shap_values: feature_importances.reduce((acc, f) => ({ ...acc, [f.feature]: parseFloat((f.importance * (Math.random() > 0.5 ? 1 : -1)).toFixed(3)) }), {}),
        };
    };

    useEffect(() => {
        const fetchAnalysis = async () => {
            try {
                setLoading(true);
                // Using port 8002 as configured
                const res = await fetch('http://localhost:8002/api/v1/analysis/investigate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        anomaly_id: anomaly.id,
                        context: {
                            metric: anomaly.metric,
                            value: anomaly.value,
                            severity: anomaly.severity
                        }
                    })
                });

                if (!res.ok) {
                    // Fallback to mock when server unavailable
                    throw new Error(`Status ${res.status}`);
                }

                const data = await res.json();
                // If response doesn't include explainability data, supplement with mock explainability
                if (data && !data.feature_importances) {
                    data.feature_importances = generateMockAnalysis(anomaly).feature_importances;
                }
                setResult(data);
            } catch (err) {
                console.warn('Analysis service unavailable, using local explainability mock.', err);
                setResult(generateMockAnalysis(anomaly));
            } finally {
                setLoading(false);
            }
        };
        fetchAnalysis();
    }, [anomaly]);

    return (
        <div className="fixed inset-y-0 right-0 w-96 bg-slate-950 border-l border-slate-800 shadow-2xl z-50 transform transition-transform duration-300 flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 backdrop-blur">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                        <span className="text-lg">🤖</span>
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-slate-100">AI Investigator</h3>
                        <div className="text-[10px] text-blue-400 uppercase tracking-wider">Automated Diagnostics</div>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
                >
                    ✕
                </button>
            </div>

            <div className="flex-1 p-6 overflow-y-auto space-y-6">
                {/* Context Card */}
                <div className="p-4 bg-slate-900/50 rounded-lg border border-slate-800 ring-1 ring-white/5">
                    <div className="flex justify-between items-start mb-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Anomaly Context</div>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${anomaly.severity === 'Critical' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'
                            }`}>
                            {anomaly.severity}
                        </span>
                    </div>
                    <div className="font-mono text-sm text-white mb-0.5">{anomaly.satellite}</div>
                    <div className="text-xs text-slate-400">{anomaly.metric}</div>
                    <div className="mt-2 pt-2 border-t border-slate-800 text-xs font-mono text-slate-300">
                        Reading: {anomaly.value}
                    </div>
                </div>

                {/* Loading State */}
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-12 space-y-4">
                        <div className="relative">
                            <div className="w-12 h-12 rounded-full border-2 border-slate-800"></div>
                            <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
                        </div>
                        <div className="text-xs text-blue-400 animate-pulse uppercase tracking-wider font-medium">Running Diagnostics...</div>
                    </div>
                ) : result ? (
                    <>
                        {/* Analysis Section */}
                        <div className="space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.5)]"></span>
                                Root Cause Analysis
                            </h4>
                            <div className="text-sm text-slate-300 leading-relaxed bg-blue-500/5 p-4 rounded-lg border border-blue-500/10 relative">
                                {/* Decorative corner */}
                                <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-blue-500/30 rounded-tl"></div>
                                {result.analysis}
                            </div>
                        </div>

                        {/* Recommendation Section */}
                        <div className="space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100">
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]"></span>
                                Remediation Plan
                            </h4>
                            <div className="text-sm text-emerald-100/90 leading-relaxed whitespace-pre-line bg-emerald-500/5 p-4 rounded-lg border border-emerald-500/10 font-mono text-xs">
                                {result.recommendation}
                            </div>
                        </div>

                        {/* Explainability Section */}
                        <div className="space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-150">
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.35)]"></span>
                                Explainability
                            </h4>

                            {result.feature_importances && result.feature_importances.length ? (
                                <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-800">
                                    {result.feature_importances.map((f) => (
                                        <div key={f.feature} className="flex items-center gap-3 text-xs py-1">
                                            <div className="w-28 text-slate-300 font-mono text-[11px] truncate">{f.feature}</div>
                                            <div className="flex-1 bg-slate-800 rounded h-3 overflow-hidden">
                                                <div style={{ width: `${Math.max(6, f.importance * 100)}%` }} className={`h-3 bg-indigo-500`} />
                                            </div>
                                            <div className="w-12 text-right text-slate-400">{(f.importance * 100).toFixed(0)}%</div>
                                        </div>
                                    ))}

                                    {result.shap_values && (
                                        <div className="mt-3 text-xs text-slate-400">
                                            <div className="text-[10px] uppercase tracking-wider mb-2">SHAP values</div>
                                            <div className="grid grid-cols-2 gap-2">
                                                {Object.entries(result.shap_values).map(([k, v]) => (
                                                    <div key={k} className="flex items-center justify-between bg-slate-800/40 p-2 rounded">
                                                        <div className="font-mono text-[11px] text-slate-300 truncate">{k}</div>
                                                        <div className={`font-bold text-[11px] ${v > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{v.toFixed(3)}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-xs text-slate-400">No explainability data available.</div>
                            )}
                        </div>

                        {/* Confidence Footer */}
                        <div className="pt-4 border-t border-slate-800 flex justify-between items-center text-xs text-slate-500">
                            <span>Model: Sentinel-V2 (Mock)</span>
                            <span className="flex items-center gap-1.5">
                                Confidence
                                <span className={`font-bold ${result.confidence > 0.8 ? 'text-emerald-400' : 'text-yellow-400'
                                    }`}>
                                    {(result.confidence * 100).toFixed(0)}%
                                </span>
                            </span>
                        </div>
                    </>
                ) : (
                    <div className="p-4 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-sm text-center">
                        Analysis service unavailable.
                    </div>
                )}
            </div>
        </div>
    );
};
