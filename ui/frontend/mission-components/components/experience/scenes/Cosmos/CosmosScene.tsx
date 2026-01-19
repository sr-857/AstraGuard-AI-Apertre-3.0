import React, { useRef } from 'react';
import { Html } from '@react-three/drei';
import styles from './CosmosScene.module.css';
import { useSceneStore } from '../../core/SceneManager';
import { useNavigation } from '../../hooks/useNavigation';
import { createNavigationAnimation } from '../../utils/navigationAnimation';
import { gsap } from 'gsap';

const CosmosScene = () => {
    const {
        currentScene,
        zoomDirection,
        getZoomOutCameraData,
        endTransition
    } = useSceneStore();

    const sceneKey = 'cosmos';
    const sceneVisible = currentScene === sceneKey;
    const containerRef = useRef<HTMLDivElement>(null);

    // Navigation logic to allow zooming through this scene to the next one
    function zoomInCosmosFunction(backwards: boolean = false) {
        // We define a simple timeline that animates the container out (zoom effect)
        // when moving forward, or keeps it visible when dealing with logic.

        const tl = gsap.timeline();

        if (containerRef.current) {
            // If zooming forward (to continent), fade out and scale up
            // If backwards is true (coming from continent back to cosmos), 
            // the navigation utils usually handle reversing the timeline or we set state.
            // But here we construct the 'forward' animation usually.

            tl.to(containerRef.current, {
                opacity: 0,
                scale: 1.5,
                duration: 2,
                ease: "power2.inOut"
            });
        } else {
            // Fallback dummy animation if ref is missing for some reason
            tl.to({}, { duration: 1 });
        }

        const animation = createNavigationAnimation({
            sceneKey: sceneKey,
            timeline: tl,
            onComplete: endTransition,
            backwards: backwards,
        });

        return () => {
            animation.cleanup();
        };
    }

    useNavigation({
        sceneKey: sceneKey,
        zoomFunction: zoomInCosmosFunction,
        isVisible: sceneVisible,
        zoomDirection: null, // Force manual navigation (stop auto-advance from inertia) so user sees the scene
        getZoomOutCameraData: getZoomOutCameraData
    });

    // Generate arrays for the items
    // Group 1: 1-10
    const group1 = Array.from({ length: 10 }, (_, i) => i + 1);

    const cosmosGroups = [
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        [20, 19, 18, 17, 16, 15, 14, 13, 12, 11],
        [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    ];

    return (
        <Html fullscreen style={{ pointerEvents: 'none', zIndex: 10 }}>
            <div className={styles.container} ref={containerRef}>
                <h1 className={styles.title}>Cosmic<sup>®</sup></h1>

                {cosmosGroups.map((group, groupIndex) => {
                    const total = cosmosGroups.length;
                    const angle = (360 / total) * groupIndex;
                    const transform = `rotate(${angle}deg) translate(55vh)`;

                    return (
                        <div
                            key={`group-${groupIndex}`}
                            className={styles.cosmos}
                            style={{ transform }}
                        >
                            {group.map((imgNum, itemIndex) => (
                                <div
                                    key={`item-${groupIndex}-${itemIndex}`}
                                    className={styles.cosmosItem}
                                    style={{ animationDelay: `${itemIndex * 0.5}s` }}
                                >
                                    <img
                                        src={`/assets/cosmos/img${imgNum}.jpg`}
                                        alt={`Cosmos ${imgNum}`}
                                    />
                                </div>
                            ))}
                        </div>
                    );
                })}
            </div>
        </Html>
    );
};

export default CosmosScene;
