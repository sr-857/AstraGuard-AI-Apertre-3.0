import React from 'react';

export const LoadingSkeleton: React.FC<{
    type: 'kpi' | 'card' | 'chart' | 'table';
    count?: number;
}> = ({ type, count = 6 }) => {
    const shapes = {
        kpi: (
            <div className="animate-shimmer p-6 rounded-2xl bg-gradient-to-r from-gray-700 via-gray-800 to-gray-700 bg-[length:200%_100%]">
                <div className="h-4 bg-gray-800 rounded w-24 mb-4" />
                <div className="h-12 bg-gray-800 rounded-full w-32 mx-auto mb-4" />
                <div className="h-3 bg-gray-800 rounded w-12 mx-auto" />
            </div>
        ),
        card: <div className="animate-shimmer h-32 rounded-xl bg-gradient-to-r from-gray-700 via-gray-800 to-gray-700" />,
        chart: <div className="animate-shimmer h-48 rounded-xl bg-gradient-to-r from-gray-700 via-gray-800 to-gray-700" />,
        table: (
            <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="animate-shimmer h-12 bg-gradient-to-r from-gray-700 via-gray-800 to-gray-700 rounded-lg" />
                ))}
            </div>
        )
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {Array.from({ length: count }).map((_, i) => (
                <div key={i}>{shapes[type]}</div>
            ))}
        </div>
    );
};
