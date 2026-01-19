'use client';

import { useCallback, useRef } from 'react';

export const useSoundscape = () => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const masterGainRef = useRef<GainNode | null>(null);

    // Nodes for Engine Hum
    const humOscRef = useRef<OscillatorNode | null>(null);
    const humFilterRef = useRef<BiquadFilterNode | null>(null);

    // Nodes for Whoosh (Noise)
    const noiseSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const noiseFilterRef = useRef<BiquadFilterNode | null>(null);
    const noiseGainRef = useRef<GainNode | null>(null);

    // Initializer
    const initAudio = useCallback(() => {
        if (!audioContextRef.current) {
            const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
            audioContextRef.current = new AudioContext();

            const masterGain = audioContextRef.current.createGain();
            masterGain.gain.value = 0.3;
            masterGain.connect(audioContextRef.current.destination);
            masterGainRef.current = masterGain;
        }
    }, []);

    const startHum = useCallback(() => {
        if (!audioContextRef.current || !masterGainRef.current) initAudio();
        const ctx = audioContextRef.current!;
        if (ctx.state === 'suspended') ctx.resume();

        if (humOscRef.current) return;

        // Low frequency "Engine" hum
        const osc = ctx.createOscillator();
        const filter = ctx.createBiquadFilter();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.value = 55; // A1 note, low rumble

        filter.type = 'lowpass';
        filter.frequency.value = 100;
        filter.Q.value = 10;

        gain.gain.value = 0.05;

        osc.connect(filter);
        filter.connect(gain);
        gain.connect(masterGainRef.current!);

        osc.start();
        humOscRef.current = osc;
        humFilterRef.current = filter;
    }, [initAudio]);

    const startWhoosh = useCallback(() => {
        if (!audioContextRef.current || !masterGainRef.current) initAudio();
        const ctx = audioContextRef.current!;

        if (noiseSourceRef.current) return;

        // Create white noise buffer
        const bufferSize = 2 * ctx.sampleRate;
        const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const output = noiseBuffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            output[i] = Math.random() * 2 - 1;
        }

        const source = ctx.createBufferSource();
        source.buffer = noiseBuffer;
        source.loop = true;

        const filter = ctx.createBiquadFilter();
        const gain = ctx.createGain();

        filter.type = 'bandpass';
        filter.frequency.value = 400;
        filter.Q.value = 1;

        gain.gain.value = 0; // Start silent

        source.connect(filter);
        filter.connect(gain);
        gain.connect(masterGainRef.current!);

        source.start();
        noiseSourceRef.current = source;
        noiseFilterRef.current = filter;
        noiseGainRef.current = gain;
    }, [initAudio]);

    const setWhooshIntensity = useCallback((intensity: number) => {
        if (!noiseGainRef.current || !noiseFilterRef.current || !audioContextRef.current) return;
        const ctx = audioContextRef.current;

        // Map intensity (0-1) to volume and frequency
        const targetGain = Math.min(intensity * 0.15, 0.2);
        const targetFreq = 400 + (intensity * 1200);

        noiseGainRef.current.gain.setTargetAtTime(targetGain, ctx.currentTime, 0.1);
        noiseFilterRef.current.frequency.setTargetAtTime(targetFreq, ctx.currentTime, 0.1);
    }, []);

    const playGeigerClick = useCallback(() => {
        if (!audioContextRef.current || !masterGainRef.current) return;
        const ctx = audioContextRef.current;
        if (ctx.state === 'suspended') ctx.resume();

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(150, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(40, ctx.currentTime + 0.01);

        gain.gain.setValueAtTime(0.02, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.01);

        osc.connect(gain);
        gain.connect(masterGainRef.current!);

        osc.start();
        osc.stop(ctx.currentTime + 0.01);
    }, []);

    const stopAll = useCallback(() => {
        humOscRef.current?.stop();
        humOscRef.current = null;
        noiseSourceRef.current?.stop();
        noiseSourceRef.current = null;
    }, []);

    return {
        initAudio,
        startHum,
        startWhoosh,
        setWhooshIntensity,
        playGeigerClick,
        stopAll,
        audioState: audioContextRef.current?.state || 'closed'
    };
};
