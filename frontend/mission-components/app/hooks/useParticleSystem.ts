import { useState, useEffect, useRef, useCallback } from 'react';
import { Particle } from '../types/security';

interface UseParticleSystemProps {
    entropy: number; // 0-100
    isCompromised: boolean;
    particleCount?: number;
}

interface UseParticleSystemReturn {
    canvasRef: React.RefObject<HTMLCanvasElement>;
    particles: Particle[];
}

const MAX_PARTICLES = 1000;

export const useParticleSystem = ({
    entropy,
    isCompromised,
    particleCount = 500,
}: UseParticleSystemProps): UseParticleSystemReturn => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [particles, setParticles] = useState<Particle[]>([]);
    const animationFrameRef = useRef<number>();

    // Initialize particles
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const count = Math.min(particleCount, MAX_PARTICLES);
        const newParticles: Particle[] = [];

        for (let i = 0; i < count; i++) {
            newParticles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 2,
                vy: (Math.random() - 0.5) * 2,
                life: 1,
                maxLife: 1,
                hue: 180 + Math.random() * 40, // Cyan-blue range
                size: 1 + Math.random() * 2,
            });
        }

        setParticles(newParticles);
        return undefined;
    }, [particleCount]);

    // Animation loop
    const animate = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Clear canvas
        ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        setParticles((prevParticles) => {
            return prevParticles.map((particle) => {
                let { x, y, vx, vy, life, hue, size } = particle;

                if (isCompromised) {
                    // Shatter effect: chaotic movement
                    vx += (Math.random() - 0.5) * 10;
                    vy += (Math.random() - 0.5) * 10;
                    life -= 0.02;
                } else {
                    // Security strings: vibrate based on entropy
                    const vibrationIntensity = entropy / 100;
                    vx += (Math.random() - 0.5) * vibrationIntensity * 0.5;
                    vy += (Math.random() - 0.5) * vibrationIntensity * 0.5;

                    // Damping for smooth movement
                    vx *= 0.98;
                    vy *= 0.98;

                    // Restore life when secure
                    if (life < 1) life += 0.01;
                }

                // Update position
                x += vx;
                y += vy;

                // Boundary wrapping
                if (x < 0) x = canvas.width;
                if (x > canvas.width) x = 0;
                if (y < 0) y = canvas.height;
                if (y > canvas.height) y = 0;

                // Respawn if dead
                if (life <= 0) {
                    x = Math.random() * canvas.width;
                    y = Math.random() * canvas.height;
                    vx = (Math.random() - 0.5) * 2;
                    vy = (Math.random() - 0.5) * 2;
                    life = 1;
                }

                // Draw particle
                const alpha = life * (entropy / 100);
                ctx.fillStyle = `hsla(${hue}, 100%, 60%, ${alpha})`;
                ctx.beginPath();
                ctx.arc(x, y, size, 0, Math.PI * 2);
                ctx.fill();

                // Draw connection lines for "security strings"
                if (!isCompromised && entropy > 70) {
                    prevParticles.forEach((other) => {
                        const dx = other.x - x;
                        const dy = other.y - y;
                        const distance = Math.sqrt(dx * dx + dy * dy);

                        if (distance < 50) {
                            const lineAlpha = (1 - distance / 50) * 0.3 * (entropy / 100);
                            ctx.strokeStyle = `hsla(${hue}, 100%, 60%, ${lineAlpha})`;
                            ctx.lineWidth = 0.5;
                            ctx.beginPath();
                            ctx.moveTo(x, y);
                            ctx.lineTo(other.x, other.y);
                            ctx.stroke();
                        }
                    });
                }

                return { ...particle, x, y, vx, vy, life };
            });
        });

        animationFrameRef.current = requestAnimationFrame(animate);
    }, [entropy, isCompromised]);

    // Start/stop animation
    useEffect(() => {
        animationFrameRef.current = requestAnimationFrame(animate);
        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [animate]);

    // Resize canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const resizeCanvas = () => {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
        };

        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        return () => window.removeEventListener('resize', resizeCanvas);
    }, []);

    return { canvasRef, particles };
};
