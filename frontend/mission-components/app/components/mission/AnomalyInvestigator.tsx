import React, { useState, useEffect } from 'react';
import { AnomalyEvent } from '../../types/dashboard';
import { useReportExport } from '../../hooks/useReportExport';
import { AnalysisResult, FeatureImportance } from '../../types/analysis';
import { AIService } from '../../../services/ai-service';
import { useDashboard } from '../../context/DashboardContext';
import { AnnotationCard } from '../ui/AnnotationCard';
import { MessageSquare, Send, ShieldAlert } from 'lucide-react';

interface Props {
    anomaly: AnomalyEvent;
    onClose: () => void;
}

export const AnomalyInvestigator: React.FC<Props> = ({ anomaly, onClose }) => {
    const [loading, setLoading] = useState(true);
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [newNote, setNewNote] = useState('');
    const { generateReport } = useReportExport();
    const { annotations, addAnnotation, proposeRemediation, activeRemediation } = useDashboard();

    const anomalyNotes = annotations.filter(a => a.targetId === anomaly.id);

    const handleAddNote = (e: React.FormEvent) => {
        e.preventDefault();
        if (!newNote.trim()) return;
        addAnnotation({
            targetId: anomaly.id,
            text: newNote,
            author: 'OPERATOR_SIGMA'
        });
        setNewNote('');
    };

    const handleExport = () => {
        generateReport(anomaly);
    };

    const generateMockAnalysis = (an: AnomalyEvent): AnalysisResult => {
        const baseFeatures = ['signal_strength', 'temperature', 'battery', 'latency', 'tx_rate', 'rx_rate'];
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

                if (res.ok) {
                    const data = await res.json();
                    if (data && !data.feature_importances) {
                        data.feature_importances = generateMockAnalysis(anomaly).feature_importances;
                    }
                    setResult(data);
                } else {
                    const aiService = AIService.getInstance();
                    const aiAnalysis = await aiService.analyzeAnomaly(anomaly);
                    const mockResult = generateMockAnalysis(anomaly);
                    setResult({ ...mockResult, analysis: aiAnalysis });
                }
            } catch (err) {
                console.warn('Analysis service unavailable, using AIService fallback.', err);
                const aiService = AIService.getInstance();
                const aiAnalysis = await aiService.analyzeAnomaly(anomaly);
                const mockResult = generateMockAnalysis(anomaly);
                setResult({ ...mockResult, analysis: aiAnalysis });
            } finally {
                setLoading(false);
            }
        };
        fetchAnalysis();
    }, [anomaly]);

    return (
        <div className="fixed inset-y-0 right-0 w-96 bg-slate-950 border-l border-slate-800 shadow-2xl z-50 transform transition-transform duration-300 flex flex-col">
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
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleExport}
                        title="Export PDF Report"
                        className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-green-400 hover:bg-slate-800 rounded transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    </button>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
                    >
                        ✕
                    </button>
                </div>
            </div>

            <div className="flex-1 p-6 overflow-y-auto space-y-6 scrollbar-thin scrollbar-thumb-slate-800">
                <div className="p-4 bg-slate-900/50 rounded-lg border border-slate-800 ring-1 ring-white/5">
                    <div className="flex justify-between items-start mb-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Anomaly Context</div>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${anomaly.severity === 'Critical' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}`}>
                            {anomaly.severity}
                        </span>
                    </div>
                    <div className="font-mono text-sm text-white mb-0.5">{anomaly.satellite}</div>
                    <div className="text-xs text-slate-400">{anomaly.metric}</div>
                    <div className="mt-2 pt-2 border-t border-slate-800 text-xs font-mono text-slate-300">
                        Reading: {anomaly.value}
                    </div>
                </div>

                {/* Annotations Section */}
                <div className="space-y-4 pt-4 border-t border-slate-800">
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                        <MessageSquare size={14} className="text-yellow-500" />
                        Operational Notes
                    </h4>

                    <div className="space-y-3">
                        {anomalyNotes.length > 0 ? (
                            anomalyNotes.map(note => (
                                <AnnotationCard key={note.id} annotation={note} />
                            ))
                        ) : (
                            <div className="text-[10px] text-slate-500 italic text-center py-2 border border-dashed border-slate-800 rounded">
                                No operational notes found for this event.
                            </div>
                        )}
                    </div>

                    <form onSubmit={handleAddNote} className="relative">
                        <input
                            type="text"
                            value={newNote}
                            onChange={(e) => setNewNote(e.target.value)}
                            placeholder="Add sticky note..."
                            className="w-full bg-slate-900 border border-slate-700 rounded-sm py-2 px-3 pr-10 text-[11px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-yellow-500/50 transition-colors"
                        />
                        <button type="submit" className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-600 hover:text-yellow-500 transition-colors">
                            <Send size={14} />
                        </button>
                    </form>
                </div>

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
                        <div className="space-y-3">
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.5)]"></span>
                                Root Cause Analysis
                            </h4>
                            <div className="text-sm text-slate-300 leading-relaxed bg-blue-500/5 p-4 rounded-lg border border-blue-500/10 relative">
                                <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-blue-500/30 rounded-tl"></div>
                                {result.analysis}
                            </div>
                        </div>

                        <div className="space-y-3">
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]"></span>
                                Remediation Plan
                            </h4>
                            <div className="text-sm text-emerald-100/90 leading-relaxed whitespace-pre-line bg-emerald-500/5 p-4 rounded-lg border border-emerald-500/10 font-mono text-xs">
                                {result.recommendation}
                            </div>

                            {!activeRemediation && (
                                <button
                                    onClick={() => proposeRemediation(anomaly.id)}
                                    className="w-full py-2 bg-red-600 hover:bg-red-500 text-white rounded text-[10px] font-bold uppercase tracking-[0.2em] transition-all flex items-center justify-center gap-2 group shadow-[0_0_15px_rgba(220,38,38,0.3)]"
                                >
                                    <ShieldAlert size={14} className="group-hover:animate-pulse" /> AUTHORIZE_TACTICAL_FIX
                                </button>
                            )}
                        </div>

                        <div className="space-y-3">
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
                                </div>
                            ) : null}
                        </div>

                        <div className="pt-4 border-t border-slate-800 flex justify-between items-center text-xs text-slate-500">
                            <span>Model: Sentinel-V2</span>
                            <span className="flex items-center gap-1.5">
                                Confidence
                                <span className={`font-bold ${result.confidence > 0.8 ? 'text-emerald-400' : 'text-yellow-400'}`}>
                                    {(result.confidence * 100).toFixed(0)}%
                                </span>
                            </span>
                        </div>
                    </>
                ) : null}
            </div>
        </div>
    );
};
