import React from 'react';
import { useMotionPreferences } from '../../utils/motion';

interface Props {
    isActive: boolean;
    children: React.ReactNode;
    className?: string;
}

export const TransitionWrapper: React.FC<Props> = ({ isActive, children, className = '' }) => {
    const { prefersReduced } = useMotionPreferences();

    return (
        <div
            className={`
        transition-all duration-500 ease-out
        ${isActive
                    ? 'scale-100 opacity-100 translate-y-0'
                    : 'scale-95 opacity-0 -translate-y-4 pointer-events-none'
                }
        ${prefersReduced ? 'motion-safe:transition-none' : ''}
        ${className}
      `}
        >
            {children}
        </div>
    );
};
