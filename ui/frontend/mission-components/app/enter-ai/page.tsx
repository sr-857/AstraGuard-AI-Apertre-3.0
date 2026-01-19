"use client";

import { useEffect, useRef } from "react";
import styles from "./styles.module.css";
import Link from "next/link";

const TOTAL_ITEMS = 20; // Based on the HTML having images img1.jpg to img20.jpg
const TOTAL_GROUPS = 4; // Based on the HTML having 4 div.cosmos groups

export default function EnterAIPage() {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        const cosmosGroups = containerRef.current.querySelectorAll(`.${styles.cosmos}`);
        const total = cosmosGroups.length;

        cosmosGroups.forEach((group, i) => {
            const angle = (360 / total) * i;
            // Using type casting for HTMLHTMLElement to access style
            (group as HTMLElement).style.transform = `rotate(${angle}deg) translate(55vh)`;

            const items = group.querySelectorAll(`.${styles.cosmosItem}`);
            items.forEach((item, j) => {
                (item as HTMLElement).style.animationDelay = `${j * 0.5}s`;
            });
        });
    }, []);

    // Helper to generate the image paths based on the original HTML structure
    // The original HTML had specific images in specific slots, but it looks like a pattern.
    // Group 1: 1-10
    // Group 2: 11-20
    // Group 3: 10-1 (reverse?) - actually checking the file, it was 10,9,8...
    // Group 4: 20-11 (reverse?)

    // Let's replicate the exact structure from the HTML file for fidelity
    const renderGroup1 = () => (
        <>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
                <div key={`g1-${num}`} className={styles.cosmosItem}>
                    <img src={`/assets/enter-ai/img${num}.jpg`} alt="" className={styles.img} />
                </div>
            ))}
        </>
    );

    const renderGroup2 = () => (
        <>
            {[11, 12, 13, 14, 15, 16, 17, 18, 19, 20].map((num) => (
                <div key={`g2-${num}`} className={styles.cosmosItem}>
                    <img src={`/assets/enter-ai/img${num}.jpg`} alt="" className={styles.img} />
                </div>
            ))}
        </>
    );

    const renderGroup3 = () => (
        <>
            {[10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((num) => (
                <div key={`g3-${num}`} className={styles.cosmosItem}>
                    <img src={`/assets/enter-ai/img${num}.jpg`} alt="" className={styles.img} />
                </div>
            ))}
        </>
    );

    const renderGroup4 = () => (
        <>
            {[20, 19, 18, 17, 16, 15, 14, 13, 12, 11].map((num) => (
                <div key={`g4-${num}`} className={styles.cosmosItem}>
                    <img src={`/assets/enter-ai/img${num}.jpg`} alt="" className={styles.img} />
                </div>
            ))}
        </>
    );


    return (
        <div className={styles.body}>
            <div className={styles.centerWrapper}>
                <Link
                    href="/dashboard"
                    className="relative px-8 py-4 border border-white/20 rounded-full font-mono text-sm tracking-widest uppercase bg-transparent backdrop-blur-sm hover:bg-white hover:text-black transition-colors duration-500 whitespace-nowrap"
                >
                    ENTER DASHBOARD
                </Link>
            </div>
            <div className={styles.container} ref={containerRef}>
                <div className={styles.cosmos}>{renderGroup1()}</div>
                <div className={styles.cosmos}>{renderGroup2()}</div>
                <div className={styles.cosmos}>{renderGroup3()}</div>
                <div className={styles.cosmos}>{renderGroup4()}</div>
            </div>
        </div>
    );
}
