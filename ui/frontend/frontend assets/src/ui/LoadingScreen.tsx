import React, { useEffect } from 'react';
import { useSceneStore } from '../core/SceneManager';

const LoadingScreen: React.FC = () => {
    const { loadingProgress, loadingText } = useSceneStore();

    // when loading - only update the progress bar in the initial loader (index.html)
    useEffect(() => {
        const initialLoader = document.getElementById('initial-loader');
        const progressBar = document.querySelector('#initial-loader .progress-bar');
        const progressGlow = document.querySelector('#initial-loader .progress-glow');
        const statusText = document.querySelector('#initial-loader .status-text');
        const loadingMessage = document.querySelector('#initial-loader .loading-message');
        if (initialLoader && progressBar && progressGlow && statusText && loadingMessage) {
            progressBar.setAttribute('style', `width: ${loadingProgress}%`);
            progressGlow.setAttribute('style', `left: ${loadingProgress}%`);
            statusText.textContent = `${Math.round(loadingProgress)}% Loaded`;
            loadingMessage.textContent = loadingText || 'Preparing your cosmic journey...';

            // when loading is complete, hide the loader
            if (initialLoader && loadingProgress >= 100) {
                setTimeout(() => {
                    initialLoader.style.opacity = '0';
                    setTimeout(() => {
                        initialLoader.style.display = 'none';
                    }, 500);
                }, 300); // small delay just in case
            } else {
                initialLoader.style.opacity = '1';
                initialLoader.style.display = 'flex';
            }
        }

        return
    }, [loadingProgress]);

    return null;
};

export default LoadingScreen;