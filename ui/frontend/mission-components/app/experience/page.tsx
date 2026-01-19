"use client";

import dynamic from 'next/dynamic';

const ExperienceRoot = dynamic(() => import('@/components/experience/ExperienceRoot'), {
    ssr: false,
    loading: () => <div className="w-full h-screen bg-black flex items-center justify-center text-white">Loading Experience...</div>
});

export default function ExperiencePage() {
    return (
        <main className="w-full h-screen bg-black overflow-hidden">
            <ExperienceRoot />
        </main>
    );
}
