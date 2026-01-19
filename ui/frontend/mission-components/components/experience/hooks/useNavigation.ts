import { useEffect } from 'react';
import { SCENE_MANAGER } from '../config/config';
import { SceneType } from '../core/SceneManager';

interface NavigationOptions {
    sceneKey: SceneType;
    zoomFunction: (backwards: boolean) => void;
    isVisible: boolean;
    zoomDirection: 'in' | 'out' | null;
    getZoomOutCameraData: (sceneKey: string) => Record<string, any>;
    minSwipeDistance?: number;
}

// Hook to handle navigation (wheel and swipe) for scene transitions
export function useNavigation({
    sceneKey,
    zoomFunction,
    isVisible,
    zoomDirection,
    getZoomOutCameraData,
    minSwipeDistance = 10
}: NavigationOptions) {
    const sceneIndex = SCENE_MANAGER.SCENE_ORDER.indexOf(sceneKey);
    const defaultCameraData = SCENE_MANAGER.ZOOM_OUT_CAMERA_DATA_DEFAULT;

    useEffect(() => {
        if (!isVisible) return;

        let cleanup: (() => void) | void | null = null;

        const isFirstScene = () => { // check if the current scene is the first scene (zoomed out)
            const zoomOutCameraData = getZoomOutCameraData(sceneKey);
            return (sceneIndex == 0 && (zoomOutCameraData && zoomOutCameraData === defaultCameraData))
        }

        // handle wheel events
        const handleInitialWheel = (event: WheelEvent) => {
            event.preventDefault();

            if (event.deltaY < 0) { // scroll up = zoom in
                removeAllListeners();
                cleanup = zoomFunction(false);
            } else if (event.deltaY > 0 && !isFirstScene()) { // scroll down = zoom out && if not the first scene
                removeAllListeners();
                cleanup = zoomFunction(true);
            }
        };

        // handle touch events
        let touchStartY = 0;

        const handleInitialTouch = (event: TouchEvent) => {
            touchStartY = event.touches[0].clientY; // save start touch position
            event.preventDefault();
        };

        const handleInitialTouchMove = (event: TouchEvent) => {
            if (!touchStartY) return;

            event.preventDefault();
            const currentY = event.touches[0].clientY;
            const deltaY = touchStartY - currentY;

            // ignore not significant swipes
            if (Math.abs(deltaY) < minSwipeDistance) return;

            // for swipe right (negative deltaX) zoom in do deltaX < 0
            // for swipe top (positive deltaY) zoom in do deltaY < 0
            if (deltaY > 0) {
                removeAllListeners();
                cleanup = zoomFunction(false);
            }
            // for swipe left (positive deltaX) zoom out do deltaX > 0 (&& if not the first scene)
            // for swipe bottom (negative deltaY) zoom out do deltaY > 0 (&& if not the first scene)
            else if (deltaY < 0 && !isFirstScene()) {
                removeAllListeners();
                cleanup = zoomFunction(true);
            }

            touchStartY = 0;
        };

        // remove all event listeners
        const removeAllListeners = () => {
            window.removeEventListener('wheel', handleInitialWheel);
            window.removeEventListener('touchstart', handleInitialTouch);
            window.removeEventListener('touchmove', handleInitialTouchMove);
        };

        // add event listeners after a small delay to prevent accidental scrolling through the scene
        const timeoutId = setTimeout(() => {
            window.addEventListener('wheel', handleInitialWheel, { passive: false });
            window.addEventListener('touchstart', handleInitialTouch, { passive: false });
            window.addEventListener('touchmove', handleInitialTouchMove, { passive: false });
        }, 1000);

        // adding inertia logic, otherwise movement (also animation & (moving) object tracking) would stop after switching the scene till you scroll again
        // if (zoomDirection === 'in') {
        //     removeAllListeners();
        //     cleanup = zoomFunction(false);
        // } else if (zoomDirection === 'out') {
        //     removeAllListeners();
        //     cleanup = zoomFunction(true);
        // }

        // clean up
        return () => {
            clearTimeout(timeoutId);
            removeAllListeners();
            if (cleanup) cleanup();
        };
    }, [isVisible]);
}