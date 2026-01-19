import { useEffect, useRef, useState } from 'react';
import { useMobile } from '../contexts/MobileContext';
import { useSceneStore } from '../core/SceneManager';
import { SCENE_MANAGER } from '../config/config';

export interface SceneText {
  header: string;
  sub: string;
  backgroundColor?: string; // background color for the text container
}

function SceneTextComponent() {
  const { currentScene, sceneZoomed } = useSceneStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const { isMobile } = useMobile();

  // calculate responsive font sizes
  const headerSize = isMobile ? '32px' : '48px';
  const subSize = isMobile ? '18px' : '24px';
  const topPosition = isMobile ? '20px' : '30px';

  // get scene text based on current scene
  const getSceneText = () => {
    switch (currentScene) {
      case 'galaxy':
        return { header: 'Milky Way', sub: 'Galaxy' };
      case 'solarSystemApproach':
        return { header: 'Interstellar Space', sub: 'Orion Arm' };
      case 'solarSystemRotation':
        return { header: 'Solar System', sub: 'Star System' };
      case 'earthApproach':
        return { header: 'Earth Vicinity', sub: 'Near Space' };
      case 'earth':
        return { header: 'Earth', sub: 'Planet' };
      case 'continent':
        return { header: 'Europe', sub: 'Continent' };
      case 'city':
        return { header: 'Hannover, Germany', sub: 'City' };
      case 'district':
        return { header: 'Mitte, Hannover', sub: 'District' };
      case 'room':
        return { header: 'My Studio', sub: 'Workspace' };
      default:
        return null;
    }
  };
  const [localText, setLocalText] = useState<SceneText | null>(getSceneText());

  useEffect(() => {
    // remove text when last scene zoomed in (cant properly see the device's content)
    if (SCENE_MANAGER.SCENE_ORDER.indexOf(currentScene) === SCENE_MANAGER.SCENE_ORDER.length - 1 && sceneZoomed === 'in') {
      setLocalText(null);
      return
    }

    const sceneText = getSceneText();
    if (sceneText?.header == localText?.header && sceneText?.sub == localText?.sub) return;

    if (sceneText) {
      setLocalText(sceneText);
    } else if (localText) { // when parent clears overlayText, clear localText.
      setLocalText(null)
    }
  }, [currentScene, sceneZoomed]);

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        top: topPosition,
        left: 0,
        right: 0,
        textAlign: 'center',
        pointerEvents: 'none',
        zIndex: 100,
        opacity: 1,
        backgroundColor: localText?.backgroundColor,
        padding: isMobile ? '0 15px' : '0',
      }}
    >
      <div style={{ fontFamily: 'Tektur-Medium', fontSize: headerSize, color: 'white' }}>
        {localText?.header}
      </div>
      <div style={{ fontFamily: 'Tektur-Regular', fontSize: subSize, color: 'gray' }}>
        {localText?.sub}
      </div>
    </div>
  );
}

export default SceneTextComponent;