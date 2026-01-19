import { Canvas } from '@react-three/fiber';
import { Preload } from '@react-three/drei';
import { Suspense } from 'react';
import SceneTextComponent from './ui/SceneText';
import { MobileProvider, useMobile } from './contexts/MobileContext';
import { useSceneStore } from './core/SceneManager';
import { AssetManager } from './core/AssetManager';
import ZoomProgressIndicator from './ui/ZoomProgressIndicator';
import { GLOBAL } from './config/config';
import NavigationHint from './ui/NavigationHint';
import LoadingScreen from './ui/LoadingScreen';
import GitHubLink from './ui/GithubLink';
import WebGLWarning from './ui/WebGLWarning';
import { useWebGL2Enabled } from './hooks/useWebGL2Support';
import { NoToneMapping } from 'three';
import { Analytics } from "@vercel/analytics/react"

// scenes
import GalaxyScene from './scenes/Galaxy/GalaxyScene';
import SolarSystemScene from './scenes/SolarSystem/SolarSystemScene';
import ContinentScene from './scenes/Continent/ContinentScene';
import CityScene from './scenes/City/CityScene';
import DistrictScene from './scenes/District/DistrictScene';
import RoomScene from './scenes/Room/RoomScene';
import ErrorBoundary from './ui/ErrorBoundary';

function AppContent() {
  const { currentScene, loadingProgress } = useSceneStore();

  const { isMobile } = useMobile();
  const isWebGL2Enabled = useWebGL2Enabled();

  // show nothing while checking WebGL enabled
  if (isWebGL2Enabled === null) {
    return null;
  }

  // if WebGL is not enabled, show the warning
  if (isWebGL2Enabled === false) {
    return <WebGLWarning />;
  }

  return (
    <>
      <Canvas camera={{ position: isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_POS : GLOBAL.INITIAL_CAMERA_DESKTOP_POS, fov: isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_FOV : GLOBAL.INITIAL_CAMERA_DESKTOP_FOV }} style={{ background: 'black' }} gl={{
        antialias: true,
        toneMapping: NoToneMapping,
        toneMappingExposure: GLOBAL.TONE_MAPPING_EXPOSURE,
        powerPreference: 'high-performance',
        pixelRatio: window.devicePixelRatio,
      }}
      >
        {/* assets preloader & scene precompiler */}
        <AssetManager />

        {/* loading screen */}
        {loadingProgress != null && loadingProgress < 100 && (<LoadingScreen />)}

        {/* scenes */}
        <Suspense fallback={<LoadingScreen />}>
          <>
            {currentScene === 'galaxy' && <GalaxyScene />}
            {['solarSystemApproach', 'solarSystemRotation', 'earthApproach', 'earth'].includes(currentScene) && <SolarSystemScene />}
            {currentScene === 'continent' && <ContinentScene />}
            {currentScene === 'city' && <CityScene />}
            {currentScene === 'district' && <DistrictScene />}
            {currentScene === 'room' && <RoomScene />}
          </>
        </Suspense>

        <Preload all />
      </Canvas>

      {/* UI */}
      {loadingProgress >= 100 && (
        <>
          {/* yeah, it was supposed to be horizontal on mobile, but I changed my mind */}
          {/* <MobileOrientationWarning /> */}
          <NavigationHint />
          <ZoomProgressIndicator />
          <SceneTextComponent />
          <GitHubLink />
        </>
      )}
    </>
  );
}

function App() {
  return (
    <>
      <ErrorBoundary>
        <MobileProvider>
          <AppContent />
        </MobileProvider>
      </ErrorBoundary>
      <Analytics />
    </>
  );
}

export default App;