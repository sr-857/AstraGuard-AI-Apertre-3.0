import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface GlitchOverlayProps {
    intensity: number; // 0-1
    isActive: boolean;
}

export const GlitchOverlay: React.FC<GlitchOverlayProps> = ({ intensity, isActive }) => {
    const [glitchLines, setGlitchLines] = React.useState<number[]>([]);

    // Generate random glitch line positions
    React.useEffect(() => {
        if (!isActive) return;

        const interval = setInterval(() => {
            const lineCount = Math.floor(intensity * 10);
            const lines = Array.from({ length: lineCount }, () => Math.random() * 100);
            setGlitchLines(lines);
        }, 100);

        return () => clearInterval(interval);
    }, [intensity, isActive]);

    if (!isActive) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 pointer-events-none z-50"
                style={{
                    mixBlendMode: 'screen',
                }}
            >
                {/* Static Noise Overlay */}
                <div
                    className="absolute inset-0"
                    style={{
                        background: `
                            repeating-linear-gradient(
                                0deg,
                                rgba(255, 255, 255, ${intensity * 0.02}) 0px,
                                transparent 1px,
                                transparent 2px,
                                rgba(255, 255, 255, ${intensity * 0.02}) 3px
                            )
                        `,
                        opacity: intensity * 0.5,
                        animation: 'scanline 8s linear infinite',
                    }}
                />

                {/* Chromatic Aberration Lines */}
                {glitchLines.map((position, index) => (
                    <motion.div
                        key={index}
                        className="absolute left-0 right-0 h-[2px]"
                        style={{
                            top: `${position}%`,
                            background: `linear-gradient(90deg, 
                                rgba(255, 0, 0, ${intensity * 0.3}), 
                                rgba(0, 255, 0, ${intensity * 0.3}), 
                                rgba(0, 0, 255, ${intensity * 0.3})
                            )`,
                            filter: 'blur(1px)',
                        }}
                        initial={{ scaleX: 0, x: '-50%' }}
                        animate={{ scaleX: 1, x: '0%' }}
                        exit={{ scaleX: 0, x: '50%' }}
                        transition={{ duration: 0.1 }}
                    />
                ))}

                {/* Horizontal Glitch Bars */}
                <motion.div
                    className="absolute inset-0"
                    style={{
                        background: `
                            repeating-linear-gradient(
                                0deg,
                                transparent,
                                transparent 2px,
                                rgba(255, 255, 255, ${intensity * 0.05}) 2px,
                                rgba(255, 255, 255, ${intensity * 0.05}) 4px
                            )
                        `,
                    }}
                    animate={{
                        y: [0, -10, 0],
                    }}
                    transition={{
                        duration: 0.5,
                        repeat: Infinity,
                        ease: 'linear',
                    }}
                />

                {/* CSS Glitch Filter */}
                <style jsx>{`
                    @keyframes scanline {
                        0% {
                            transform: translateY(0);
                        }
                        100% {
                            transform: translateY(100vh);
                        }
                    }
                `}</style>
            </motion.div>
        </AnimatePresence>
    );
};
