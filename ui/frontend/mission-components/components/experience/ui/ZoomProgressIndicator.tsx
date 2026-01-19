import { useEffect, useState } from 'react';
import { useSceneStore } from '../core/SceneManager';
import styles from './ZoomProgressIndicator.module.css';
import { SCENE_MANAGER } from '../config/config';
import { useMobile } from '../contexts/MobileContext';

const ZoomProgressIndicator = () => {
  const { zoomDirection, currentScene } = useSceneStore();

  const [zoomProgress, setZoomProgress] = useState(0);
  const [lastScene, setLastScene] = useState(currentScene);

  const { isMobile } = useMobile();

  useEffect(() => {
    // subscribe to progress updates from navigation animation
    const handleProgressUpdate = (event: CustomEvent<{ progress: number }>) => {
      if (event.detail && typeof event.detail.progress === 'number') {
        setZoomProgress(event.detail.progress);
      }
    };

    window.addEventListener('zoom-progress-update', handleProgressUpdate as EventListener);
    return () => window.removeEventListener('zoom-progress-update', handleProgressUpdate as EventListener);
  }, []);

  // reset zoom progress when the scene changes
  useEffect(() => {
    setZoomProgress(['in', null].includes(zoomDirection) ? 0 : 1);
  }, [currentScene])

  const sceneOrder = SCENE_MANAGER.SCENE_ORDER.concat(['end']);  // add 'end' to the end of the last scene for zoomed in state

  // calculate overall progress (all scenes) based on scene index and zoom progress
  const calculateOverallProgress = () => {
    const sceneIndex = sceneOrder.indexOf(currentScene);
    if (sceneIndex === -1) return 0;

    // each scene represents a segment of the total progress
    const segmentSize = 100 / (sceneOrder.length - 1);
    const baseProgress = sceneIndex * segmentSize;

    // add the progress within the current scene
    let currentSceneProgress = 0;

    if (lastScene !== currentScene) {
      setLastScene(currentScene); // update last scene to current scene

      currentSceneProgress = ['in', null].includes(zoomDirection) ? 0 : 1 // if zooming in, set progress to 0, out - to 1
      setZoomProgress(currentSceneProgress);
    } else {
      currentSceneProgress = zoomProgress * segmentSize;
    }

    return baseProgress + currentSceneProgress;
  };

  const overallProgress = calculateOverallProgress();

  return (
    <div className={`${styles['zoom-progress-container']} ${isMobile ? styles['mobile'] : ''}`}>
      <div className={styles['zoom-progress-line']}></div>

      {sceneOrder.map((scene, index) => {
        const position = (index / (sceneOrder.length - 1)) * 100;
        const isActive = sceneOrder.indexOf(currentScene) >= index;
        const icon = SCENE_MANAGER.SCENE_ASSETS.icons.zoomProgressIndicator[scene as keyof typeof SCENE_MANAGER.SCENE_ASSETS.icons.zoomProgressIndicator];

        return (
          <div
            key={scene}
            className={`${styles['scene-marker']} ${isActive ? styles['active'] : ''}`}
            style={{ 'top': `${position}%` }}
          >
            {icon && (
              <div className={styles['marker-icon']}
                style={{ backgroundImage: `url(${icon})` }} />
            )}
          </div>
        );
      })}

      <div
        className={styles['zoom-progress-indicator']}
        style={{ 'top': `${overallProgress}%` }}
      >
        <img
          src={sceneOrder.indexOf(currentScene) < 5 ?
            SCENE_MANAGER.SCENE_ASSETS.icons.zoomProgressIndicator.astronaut :
            (sceneOrder.indexOf(currentScene) < 8 ?
              SCENE_MANAGER.SCENE_ASSETS.icons.zoomProgressIndicator.superhero :
              SCENE_MANAGER.SCENE_ASSETS.icons.zoomProgressIndicator.human)}
          alt="Current progress"
          className={styles['indicator-icon']}
        />
      </div>
    </div>
  );
};

export default ZoomProgressIndicator;