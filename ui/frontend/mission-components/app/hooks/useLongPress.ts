import { useState, useEffect, useCallback, useRef } from 'react';

interface UseLongPressOptions {
    threshold?: number; // Duration in milliseconds (default: 3000)
    onStart?: () => void;
    onFinish?: () => void;
    onCancel?: () => void;
}

interface UseLongPressReturn {
    onMouseDown: () => void;
    onMouseUp: () => void;
    onMouseLeave: () => void;
    onTouchStart: () => void;
    onTouchEnd: () => void;
    isPressed: boolean;
    progress: number; // 0-100
}

export const useLongPress = ({
    threshold = 3000,
    onStart,
    onFinish,
    onCancel,
}: UseLongPressOptions): UseLongPressReturn => {
    const [isPressed, setIsPressed] = useState(false);
    const [progress, setProgress] = useState(0);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const startTimeRef = useRef<number>(0);

    const start = useCallback(() => {
        setIsPressed(true);
        startTimeRef.current = Date.now();
        onStart?.();

        // Update progress every 50ms
        progressIntervalRef.current = setInterval(() => {
            const elapsed = Date.now() - startTimeRef.current;
            const newProgress = Math.min((elapsed / threshold) * 100, 100);
            setProgress(newProgress);
        }, 50);

        // Trigger finish callback when threshold is reached
        timerRef.current = setTimeout(() => {
            setIsPressed(false);
            setProgress(100);
            onFinish?.();
            cleanup();
        }, threshold);
    }, [threshold, onStart, onFinish]);

    const cancel = useCallback(() => {
        if (isPressed) {
            setIsPressed(false);
            setProgress(0);
            onCancel?.();
            cleanup();
        }
    }, [isPressed, onCancel]);

    const cleanup = () => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
        if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
        }
    };

    useEffect(() => {
        return () => cleanup();
    }, []);

    return {
        onMouseDown: start,
        onMouseUp: cancel,
        onMouseLeave: cancel,
        onTouchStart: start,
        onTouchEnd: cancel,
        isPressed,
        progress,
    };
};
