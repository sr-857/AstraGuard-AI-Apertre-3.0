import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Circle, AlertTriangle, Loader2, X, Play } from 'lucide-react';
import { IncidentPlaybook as PlaybookType, RemediationStep, StepStatus } from '../../types/playbook';
import { useCommandExecution } from '../../hooks/useCommandExecution';

interface IncidentPlaybookProps {
    playbook: PlaybookType | null;
    onDismiss: () => void;
    onStepComplete: (stepId: string) => void;
    onHighlightPanel: (panelId: string | null) => void;
}

export const IncidentPlaybook: React.FC<IncidentPlaybookProps> = ({
    playbook,
    onDismiss,
    onStepComplete,
    onHighlightPanel,
}) => {
    const { executeCommand, executionStatus, isExecuting } = useCommandExecution();
    const [localSteps, setLocalSteps] = React.useState<RemediationStep[]>([]);

    React.useEffect(() => {
        if (playbook) {
            setLocalSteps(playbook.steps);
        }
    }, [playbook]);

    const handleExecuteStep = async (step: RemediationStep) => {
        // Highlight target panel if specified
        if (step.targetPanel) {
            onHighlightPanel(step.targetPanel);
        }

        const result = await executeCommand(step.command, step.id);

        if (result.success) {
            setLocalSteps((prev) =>
                prev.map((s) =>
                    s.id === step.id ? { ...s, status: StepStatus.COMPLETED } : s
                )
            );
            onStepComplete(step.id);

            // Clear panel highlight after completion
            setTimeout(() => onHighlightPanel(null), 2000);
        } else {
            setLocalSteps((prev) =>
                prev.map((s) =>
                    s.id === step.id
                        ? { ...s, status: StepStatus.FAILED, errorMessage: result.message }
                        : s
                )
            );
        }
    };

    const getStepIcon = (status: StepStatus) => {
        switch (status) {
            case StepStatus.COMPLETED:
                return <CheckCircle2 className="w-5 h-5 text-green-400" />;
            case StepStatus.IN_PROGRESS:
                return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
            case StepStatus.FAILED:
                return <AlertTriangle className="w-5 h-5 text-red-400" />;
            default:
                return <Circle className="w-5 h-5 text-gray-400" />;
        }
    };

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'CRITICAL':
                return 'border-red-500/50 bg-red-500/10';
            case 'HIGH':
                return 'border-orange-500/50 bg-orange-500/10';
            case 'MEDIUM':
                return 'border-yellow-500/50 bg-yellow-500/10';
            default:
                return 'border-cyan-500/50 bg-cyan-500/10';
        }
    };

    const completedSteps = localSteps.filter((s) => s.status === StepStatus.COMPLETED).length;
    const totalSteps = localSteps.length;
    const progress = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;

    if (!playbook) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ x: 500, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: 500, opacity: 0 }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                className="fixed right-6 top-24 w-96 max-h-[80vh] z-50"
            >
                <div
                    className={`backdrop-blur-xl border-2 rounded-xl shadow-2xl overflow-hidden ${getSeverityColor(
                        playbook.severity
                    )}`}
                    style={{
                        background: 'linear-gradient(135deg, rgba(0,0,0,0.9) 0%, rgba(20,20,40,0.95) 100%)',
                    }}
                >
                    {/* Header */}
                    <div className="p-4 border-b border-white/10">
                        <div className="flex items-start justify-between mb-3">
                            <div>
                                <h3 className="text-lg font-bold text-white uppercase tracking-wider mb-1">
                                    {playbook.title}
                                </h3>
                                <p className="text-xs text-white/60 uppercase tracking-widest">
                                    AI Remediation Playbook
                                </p>
                            </div>
                            <button
                                onClick={onDismiss}
                                className="p-1 hover:bg-white/10 rounded transition-colors"
                            >
                                <X className="w-5 h-5 text-white/60" />
                            </button>
                        </div>

                        {/* Progress Bar */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-xs text-white/60">
                                <span>Progress</span>
                                <span>
                                    {completedSteps} / {totalSteps} Steps
                                </span>
                            </div>
                            <div className="h-2 bg-black/30 rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${progress}%` }}
                                    transition={{ duration: 0.5 }}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Steps List */}
                    <div className="max-h-[60vh] overflow-y-auto p-4 space-y-3">
                        {localSteps.map((step, index) => (
                            <motion.div
                                key={step.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.1 }}
                                className={`p-3 rounded-lg border ${step.status === StepStatus.COMPLETED
                                        ? 'border-green-500/30 bg-green-500/5'
                                        : step.status === StepStatus.FAILED
                                            ? 'border-red-500/30 bg-red-500/5'
                                            : 'border-white/10 bg-white/5'
                                    }`}
                            >
                                <div className="flex items-start gap-3">
                                    <div className="mt-0.5">{getStepIcon(step.status)}</div>
                                    <div className="flex-1">
                                        <p className="text-sm text-white font-medium mb-2">{step.description}</p>

                                        {step.targetPanel && (
                                            <p className="text-xs text-cyan-400 mb-2">
                                                → Target: {step.targetPanel}
                                            </p>
                                        )}

                                        {step.status === StepStatus.FAILED && step.errorMessage && (
                                            <p className="text-xs text-red-400 mb-2">Error: {step.errorMessage}</p>
                                        )}

                                        {step.status === StepStatus.PENDING && (
                                            <button
                                                onClick={() => handleExecuteStep(step)}
                                                disabled={isExecuting}
                                                className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/50 rounded text-xs text-cyan-400 font-bold uppercase tracking-wider transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <Play className="w-3 h-3" />
                                                Execute Command
                                            </button>
                                        )}

                                        {step.estimatedDuration && step.status === StepStatus.PENDING && (
                                            <p className="text-xs text-white/40 mt-2">
                                                Est. {step.estimatedDuration}s
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>

                    {/* Footer */}
                    {progress === 100 && (
                        <div className="p-4 border-t border-white/10 bg-green-500/10">
                            <p className="text-sm text-green-400 font-bold text-center">
                                ✓ All remediation steps completed!
                            </p>
                        </div>
                    )}
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
