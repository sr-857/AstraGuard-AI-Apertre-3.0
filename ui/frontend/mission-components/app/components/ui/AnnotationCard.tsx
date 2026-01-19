'use client';

import React from 'react';
import { Annotation, useDashboard } from '../../context/DashboardContext';
import { X, User, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

interface Props {
    annotation: Annotation;
}

export const AnnotationCard: React.FC<Props> = ({ annotation }) => {
    const { removeAnnotation } = useDashboard();

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-sm relative group hover:bg-yellow-500/20 transition-colors"
        >
            <button
                onClick={() => removeAnnotation(annotation.id)}
                className="absolute top-1 right-1 p-1 text-yellow-500/50 hover:text-yellow-500 opacity-0 group-hover:opacity-100 transition-opacity"
            >
                <X size={12} />
            </button>

            <div className="flex items-center gap-2 mb-2">
                <div className="w-5 h-5 rounded-full bg-yellow-500/20 flex items-center justify-center text-[10px] text-yellow-500 font-bold border border-yellow-500/30">
                    <User size={10} />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-bold text-yellow-500 uppercase tracking-tighter truncate">
                        {annotation.author}
                    </div>
                    <div className="flex items-center gap-1 text-[8px] text-yellow-500/60 font-mono">
                        <Clock size={8} />
                        {annotation.timestamp}
                    </div>
                </div>
            </div>

            <p className="text-[11px] text-yellow-100/90 leading-relaxed italic">
                "{annotation.text}"
            </p>

            {/* Sticky note tape effect */}
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-8 h-2 bg-yellow-500/20 border-x border-yellow-500/30 rotate-2" />
        </motion.div>
    );
};
