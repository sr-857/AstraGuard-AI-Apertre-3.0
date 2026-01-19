import { useState, useCallback } from 'react';
import { CommandExecutionResult, StepStatus } from '../types/playbook';

interface UseCommandExecutionReturn {
    executeCommand: (command: string, stepId: string) => Promise<CommandExecutionResult>;
    executionStatus: Record<string, StepStatus>;
    isExecuting: boolean;
}

export const useCommandExecution = (): UseCommandExecutionReturn => {
    const [executionStatus, setExecutionStatus] = useState<Record<string, StepStatus>>({});
    const [isExecuting, setIsExecuting] = useState(false);

    const executeCommand = useCallback(async (command: string, stepId: string): Promise<CommandExecutionResult> => {
        setIsExecuting(true);
        setExecutionStatus((prev) => ({ ...prev, [stepId]: StepStatus.IN_PROGRESS }));

        try {
            // In production, this would call the actual backend API
            const response = await fetch('http://localhost:8002/api/v1/uplink', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command }),
            });

            if (!response.ok) {
                throw new Error(`Command execution failed: ${response.statusText}`);
            }

            const data = await response.json();

            setExecutionStatus((prev) => ({ ...prev, [stepId]: StepStatus.COMPLETED }));
            setIsExecuting(false);

            return {
                success: true,
                message: 'Command executed successfully',
                data,
            };
        } catch (error) {
            console.error('Command execution error:', error);

            setExecutionStatus((prev) => ({ ...prev, [stepId]: StepStatus.FAILED }));
            setIsExecuting(false);

            return {
                success: false,
                message: error instanceof Error ? error.message : 'Unknown error occurred',
            };
        }
    }, []);

    return {
        executeCommand,
        executionStatus,
        isExecuting,
    };
};
