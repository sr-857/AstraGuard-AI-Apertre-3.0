import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

interface PanelHighlightProps {
    targetPanelId: string | null;
    description?: string;
}

export const PanelHighlight: React.FC<PanelHighlightProps> = ({ targetPanelId, description }) => {
    const [targetElement, setTargetElement] = React.useState<HTMLElement | null>(null);
    const [position, setPosition] = React.useState<{ top: number; left: number; width: number; height: number } | null>(
        null
    );

    React.useEffect(() => {
        if (!targetPanelId) {
            setTargetElement(null);
            setPosition(null);
            return;
        }

        const element = document.getElementById(targetPanelId);
        if (element) {
            setTargetElement(element);

            const updatePosition = () => {
                const rect = element.getBoundingClientRect();
                setPosition({
                    top: rect.top,
                    left: rect.left,
                    width: rect.width,
                    height: rect.height,
                });
            };

            updatePosition();
            window.addEventListener('resize', updatePosition);
            window.addEventListener('scroll', updatePosition);

            return () => {
                window.removeEventListener('resize', updatePosition);
                window.removeEventListener('scroll', updatePosition);
            };
        }
    }, [targetPanelId]);

    if (!targetElement || !position) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 pointer-events-none z-40"
            >
                {/* Animated Border/Glow */}
                <motion.div
                    className="absolute border-4 border-cyan-400 rounded-lg"
                    style={{
                        top: position.top - 8,
                        left: position.left - 8,
                        width: position.width + 16,
                        height: position.height + 16,
                        boxShadow: '0 0 30px rgba(34, 211, 238, 0.6), inset 0 0 30px rgba(34, 211, 238, 0.3)',
                    }}
                    animate={{
                        boxShadow: [
                            '0 0 30px rgba(34, 211, 238, 0.6), inset 0 0 30px rgba(34, 211, 238, 0.3)',
                            '0 0 50px rgba(34, 211, 238, 0.8), inset 0 0 50px rgba(34, 211, 238, 0.5)',
                            '0 0 30px rgba(34, 211, 238, 0.6), inset 0 0 30px rgba(34, 211, 238, 0.3)',
                        ],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />

                {/* Arrow Pointer */}
                <motion.div
                    className="absolute flex items-center gap-2"
                    style={{
                        top: position.top + position.height / 2 - 20,
                        left: position.left - 150,
                    }}
                    initial={{ x: -20, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: 0.3 }}
                >
                    {description && (
                        <div className="px-3 py-2 bg-cyan-500/20 border border-cyan-500/50 rounded-lg backdrop-blur-xl">
                            <p className="text-sm text-cyan-400 font-bold whitespace-nowrap">{description}</p>
                        </div>
                    )}
                    <motion.div
                        animate={{ x: [0, 10, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                    >
                        <ArrowRight className="w-8 h-8 text-cyan-400" />
                    </motion.div>
                </motion.div>

                {/* Corner Markers */}
                {[
                    { top: position.top - 12, left: position.left - 12 },
                    { top: position.top - 12, left: position.left + position.width + 4 },
                    { top: position.top + position.height + 4, left: position.left - 12 },
                    { top: position.top + position.height + 4, left: position.left + position.width + 4 },
                ].map((corner, index) => (
                    <motion.div
                        key={index}
                        className="absolute w-4 h-4 border-2 border-cyan-400"
                        style={{
                            top: corner.top,
                            left: corner.left,
                            borderRadius: '2px',
                        }}
                        animate={{
                            scale: [1, 1.2, 1],
                            opacity: [0.6, 1, 0.6],
                        }}
                        transition={{
                            duration: 1.5,
                            repeat: Infinity,
                            delay: index * 0.1,
                        }}
                    />
                ))}
            </motion.div>
        </AnimatePresence>
    );
};
