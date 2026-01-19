import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface DashboardDimOverlayProps {
    isActive: boolean;
}

export const DashboardDimOverlay: React.FC<DashboardDimOverlayProps> = ({ isActive }) => {
    if (!isActive) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 pointer-events-none z-40"
                style={{
                    background: `
                        radial-gradient(
                            circle at top right,
                            rgba(0, 0, 0, 0.3) 0%,
                            rgba(0, 0, 0, 0.7) 40%,
                            rgba(0, 0, 0, 0.9) 100%
                        )
                    `,
                }}
            >
                {/* Red Tint Overlay */}
                <div
                    className="absolute inset-0"
                    style={{
                        background: 'radial-gradient(circle at top right, rgba(139, 0, 0, 0.2), transparent 60%)',
                        mixBlendMode: 'multiply',
                    }}
                />

                {/* Animated Vignette */}
                <motion.div
                    className="absolute inset-0"
                    style={{
                        background: `
                            radial-gradient(
                                circle at top right,
                                transparent 10%,
                                rgba(0, 0, 0, 0.8) 70%
                            )
                        `,
                    }}
                    animate={{
                        opacity: [0.8, 1, 0.8],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />

                {/* Scanline Effect */}
                <motion.div
                    className="absolute inset-0"
                    style={{
                        backgroundImage: `
                            repeating-linear-gradient(
                                0deg,
                                rgba(255, 0, 0, 0.03),
                                rgba(255, 0, 0, 0.03) 1px,
                                transparent 1px,
                                transparent 2px
                            )
                        `,
                    }}
                    animate={{
                        y: [0, 10, 0],
                    }}
                    transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: 'linear',
                    }}
                />
            </motion.div>
        </AnimatePresence>
    );
};
