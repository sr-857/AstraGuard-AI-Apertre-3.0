import { useCallback, useRef, useEffect } from 'react';

export const useSoundEffects = () => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const carrierRef = useRef<OscillatorNode | null>(null);
    const tensionRef = useRef<OscillatorNode | null>(null);
    const gainRef = useRef<GainNode | null>(null);
    const tensionGainRef = useRef<GainNode | null>(null);
    const lfoRef = useRef<OscillatorNode | null>(null);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
            audioContextRef.current = new AudioContext();
        }
        return () => stopDrone();
    }, []);

    const startDrone = useCallback(() => {
        if (!audioContextRef.current) return;
        const ctx = audioContextRef.current;
        if (ctx.state === 'suspended') ctx.resume();

        // Avoid multiple starts
        if (carrierRef.current) return;

        // 1. Master Gain (Volume)
        const masterGain = ctx.createGain();
        masterGain.gain.value = 0.05; // Low ambient
        masterGain.connect(ctx.destination);
        gainRef.current = masterGain;

        // 2. Carrier Oscillator (The "Hum")
        const carrier = ctx.createOscillator();
        carrier.type = 'sine';
        carrier.frequency.value = 60; // 60Hz Low hum
        carrier.connect(masterGain);
        carrier.start();
        carrierRef.current = carrier;

        // 3. LFO (Breathing effect) - Amplitute Modulation
        const lfo = ctx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 0.1; // 10 seconds per breath
        const lfoGain = ctx.createGain();
        lfoGain.gain.value = 0.02; // Depth of breath
        lfo.connect(lfoGain);
        lfoGain.connect(masterGain.gain);
        lfo.start();
        lfoRef.current = lfo;

        // 4. Tension Oscillator (The "Alarm" texture)
        const tension = ctx.createOscillator();
        tension.type = 'sawtooth';
        tension.frequency.value = 100; // Dissonant interval
        const tensionGain = ctx.createGain();
        tensionGain.gain.value = 0; // Start silent
        tension.connect(tensionGain);
        tensionGain.connect(ctx.destination); // Direct out, bypass master LFO for starkness
        tension.start();
        tensionRef.current = tension;
        tensionGainRef.current = tensionGain;
    }, []);

    const stopDrone = useCallback(() => {
        const ctx = audioContextRef.current;
        if (!ctx) return;

        // Ramp down
        if (gainRef.current) {
            gainRef.current.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1);
        }
        if (tensionGainRef.current) {
            tensionGainRef.current.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1);
        }

        setTimeout(() => {
            carrierRef.current?.stop();
            tensionRef.current?.stop();
            lfoRef.current?.stop();
            carrierRef.current = null;
            tensionRef.current = null;
            lfoRef.current = null;
        }, 1200);
    }, []);

    const updateDrone = useCallback((cpuLoad: number, anomalyCount: number) => {
        if (!audioContextRef.current || !carrierRef.current) return;
        const ctx = audioContextRef.current;

        // Map CPU Load (0-100) to Pitch (60Hz - 120Hz)
        const targetPitch = 60 + (cpuLoad * 0.6);
        carrierRef.current.frequency.setTargetAtTime(targetPitch, ctx.currentTime, 1);

        // Map Anomalies to Tension Volume & Detune
        const tensionVolume = Math.min(anomalyCount * 0.05, 0.2); // Cap at 0.2
        tensionGainRef.current?.gain.setTargetAtTime(tensionVolume, ctx.currentTime, 0.5);

        if (anomalyCount > 0) {
            // Add dissonant detune based on severity
            tensionRef.current?.frequency.setTargetAtTime(100 + (anomalyCount * 13), ctx.currentTime, 0.2);
        } else {
            tensionRef.current?.frequency.setTargetAtTime(100, ctx.currentTime, 2);
        }

    }, []);

    const playTone = (freq: number, type: OscillatorType, duration: number, volume: number = 0.1) => {
        if (!audioContextRef.current) return;
        const ctx = audioContextRef.current;

        // Resume if suspended (common browser policy)
        if (ctx.state === 'suspended') ctx.resume();

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, ctx.currentTime);

        gain.gain.setValueAtTime(volume, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + duration);
    };

    const playClick = useCallback(() => {
        // High pitched "chirp" for UI interaction
        playTone(1200, 'sine', 0.1, 0.05);
        setTimeout(() => playTone(2000, 'triangle', 0.05, 0.02), 50);
    }, []);

    const playAlert = useCallback((severity: 'low' | 'high' = 'high') => {
        // Warning beep
        if (severity === 'high') {
            playTone(880, 'square', 0.2, 0.1);
            setTimeout(() => playTone(660, 'square', 0.2, 0.1), 200);
        } else {
            playTone(440, 'sine', 0.3, 0.05);
        }
    }, []);

    const playKeystroke = useCallback(() => {
        // Soft mechanical click
        playTone(600, 'triangle', 0.03, 0.02);
    }, []);

    const playSuccess = useCallback(() => {
        // Ascending chime
        playTone(500, 'sine', 0.2, 0.05);
        setTimeout(() => playTone(1000, 'sine', 0.4, 0.05), 100);
    }, []);

    const playProximityBeep = useCallback((distance: number) => {
        // Parking sensor style beep - frequency increases as distance decreases
        // Distance range: 5-50km
        // Beep interval: 2000ms at 50km → 200ms at 5km
        const clampedDistance = Math.max(5, Math.min(50, distance));
        const interval = 200 + ((clampedDistance - 5) / 45) * 1800;

        // Higher pitch for closer objects
        const frequency = 800 - ((clampedDistance - 5) / 45) * 400; // 800Hz at 5km → 400Hz at 50km

        playTone(frequency, 'square', 0.1, 0.05);

        return interval;
    }, []);

    return { playClick, playAlert, playKeystroke, playSuccess, playProximityBeep, startDrone, stopDrone, updateDrone };
};
