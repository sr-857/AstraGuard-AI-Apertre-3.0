import { createPortal, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useState } from 'react';
import { Scene, WebGLRenderTarget } from 'three';

// How does it work:
// 1. Create a minimal scene for each scene
// 2. Render all scenes to a 1x1 pixel canvas to trigger shader & material compilation

// So we render similar materials here, and then, when the real scene renders, the GPU says: 
// "I've already compiled shaders for this exact material type and configuration - I'll reuse them!"
export function ScenePrecompiler({ scene, updateProgress }: {
  scene: JSX.Element; // scene component to be precompiled
  updateProgress: () => void; // function to update loading progress (from AssetManager)
}) {
  const { gl, camera } = useThree();
  const [isCompiled, setIsCompiled] = useState(false);

  // create an offscreen scene
  const virtualScene = useMemo(() => new Scene(), []);
  const renderTarget = useMemo(() => new WebGLRenderTarget(1, 1), []);

  // compile after children are rendered to virtual scene
  useEffect(() => {
    if (isCompiled) return;

    const timeoutId = setTimeout(() => {
      try {
        // render to offscreen buffer to trigger shader compilation
        const originalRenderTarget = gl.getRenderTarget();
        gl.setRenderTarget(renderTarget);
        gl.render(virtualScene, camera);
        gl.setRenderTarget(originalRenderTarget);

        // force compile the shaders
        gl.compile(virtualScene, camera);

        setIsCompiled(true);
      } catch (error) {
        console.error("Error during shader precompilation:", error);
      }

      updateProgress();
    }, 200); // short delay to ensure children have rendered

    return () => clearTimeout(timeoutId);
  }, [gl, camera, virtualScene, renderTarget, isCompiled]);

  // cleanup
  useEffect(() => {
    return () => {
      renderTarget.dispose();
    };
  }, [renderTarget]);

  // portal the children into the virtual scene for compilation
  return (
    <>
      {!isCompiled && createPortal(scene, virtualScene)}
    </>
  );
}