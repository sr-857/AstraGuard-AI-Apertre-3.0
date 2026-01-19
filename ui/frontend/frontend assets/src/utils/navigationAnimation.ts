import { NAVIGATION_ANIMATION } from "../config/config";
import { useSceneStore } from "../core/SceneManager";

// Creates and controls wheel/touch-based animation for a GSAP timeline
export function createNavigationAnimation({
  sceneKey,
  timeline,
  onComplete,
  backwards,
  zoomDirections = { in: true, out: true },
  friction = NAVIGATION_ANIMATION.DEFAULT_FRICTION,
  acceleration = NAVIGATION_ANIMATION.DEFAULT_ACCELERATION,
  wheelSensitivity = NAVIGATION_ANIMATION.DEFAULT_WHEEL_SENSITIVITY,
  touchSensitivity = NAVIGATION_ANIMATION.DEFAULT_TOUCH_SENSITIVITY
}: {
  sceneKey: string, timeline: GSAPTimeline,
  onComplete?: (isZoomIn: boolean) => void,
  backwards?: boolean, zoomDirections?: { in: boolean, out: boolean },
  friction?: number, acceleration?: number, initialProgress?: number,
  initialJump?: number, wheelSensitivity?: number,
  touchSensitivity?: number
}) {
  const initialProgress = backwards ? 1 : 0; // set initial progress for backwards animation
  const initialJump = backwards ? 1 : 0; // set initial jump for backwards animation

  const animState = {
    progress: initialProgress,
    targetProgress: initialJump,
    velocity: 0,
    active: true
  };
  let isZoomIn: boolean | null = !backwards;
  const { setSceneZoomed } = useSceneStore.getState();

  // animation loop with a little spring physics (kinda inertia)
  const smoothAnimationLoop = () => {
    if (!animState.active) return;

    // spring physics calculation
    const delta = animState.targetProgress - animState.progress;
    animState.velocity += delta * acceleration;
    animState.velocity *= friction;

    // set velocity to a small value to prevent it from stopping completely and follow the object (run timeline onUpdate function)
    if (Math.abs(animState.velocity) < NAVIGATION_ANIMATION.VELOCITY_THRESHOLD) {
      animState.velocity = !backwards ? NAVIGATION_ANIMATION.VELOCITY_THRESHOLD : -NAVIGATION_ANIMATION.VELOCITY_THRESHOLD;
    }

    animState.progress += animState.velocity;

    // clamp values to valid range
    animState.progress = Math.max(0, Math.min(1, animState.progress));

    timeline.progress(animState.progress); // update the timeline

    // dispatch progress event for the zoom indicator
    window.dispatchEvent(new CustomEvent('zoom-progress-update', {
      detail: {
        progress: animState.progress,
      }
    }));

    // set sceneZoomed
    if (setSceneZoomed) {
      if (animState.progress >= (1 - (NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY * NAVIGATION_ANIMATION.ZOOMED_IN_SENSITIVITY_MULTIPLIER))) {
        setSceneZoomed('in');
      }
      else if (animState.progress <= (0 + NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY)) {
        setSceneZoomed('out');
      } else {
        setSceneZoomed(null); // reset zoom state if not in/out
      }
    }

    // check for completion (progress close to 0 or 1)
    if (
      isZoomIn && animState.progress >= (1 - NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY) && zoomDirections.in
      ||
      isZoomIn === false && animState.progress <= (0 + NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY) && zoomDirections.out
    ) {
      if (animState.progress >= (1 - NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY) && zoomDirections.in) {
        if (onComplete) {
          console.debug("Animation complete - zoomed in from", sceneKey);
          onComplete(isZoomIn = true); // zoom in complete
        }
      }
      else {
        if (onComplete) {
          console.debug("Animation complete - zoomed out from", sceneKey);
          onComplete(isZoomIn = false); // zoom out complete
        }
      }

      animState.active = false;
      return;
    }

    requestAnimationFrame(smoothAnimationLoop); // continue animation loop
  };

  // process input events (wheel and touch)
  const processInput = (delta: number, sensitivity: number) => {
    // check if the current scene is the last scene and fullscreen is active
    const { isFullscreenActive } = useSceneStore.getState();
    if (isFullscreenActive) return;

    if (!animState.active) { // restart animation loop if stopped
      animState.active = true;
      requestAnimationFrame(smoothAnimationLoop);
    }

    const absDelta = Math.abs(delta);
    let normalizedDelta = absDelta < 0.001 ? 0 : (delta / (absDelta * 10)) * sensitivity;

    // it prevents zooming bugs when events stutter because of fps drops or so (for example: you zoom in, but the animation goes in, immidiately out, and then in again - it's because touch event gets wrong values in a moment)
    if (!backwards && animState.progress <= NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY) { // if just zoomed in and the progress in too small (at the most beginning of the animation) - make the input always zoom in to go out of sensivity sone
      normalizedDelta = -Math.abs(normalizedDelta); // zoom in only (force normalizedDelta to be negative)
    } else if (backwards && animState.progress >= (1 - NAVIGATION_ANIMATION.COMPLETION_SENSITIVITY)) { // if just zoomed out and the progress in too big (at the most end of the animation) - make the input always zoom out to go out of sensivity sone
      normalizedDelta = Math.abs(normalizedDelta); // zoom out only (force normalizedDelta to be positive)
    }

    isZoomIn = normalizedDelta < 0; // zoom in if delta is negative

    animState.targetProgress -= normalizedDelta;

    animState.targetProgress = Math.min(1, Math.max(0, animState.targetProgress || 0));
  };

  // handle wheel events
  const handleWheel = (event: WheelEvent) => {
    event.preventDefault();

    const delta = event.deltaY || event.detail;
    processInput(delta * (event.deltaMode === 1 ? 25 : 1), wheelSensitivity);
  };

  // touch event handlers
  let touchStartY = 0;
  let lastTouchY = 0;
  let touchVelocity = 0;
  let lastTouchTime = 0;

  const handleTouchStart = (event: TouchEvent) => {
    touchStartY = event.touches[0].clientY;
    lastTouchY = touchStartY;
    lastTouchTime = Date.now();
    event.preventDefault();
  };

  const handleTouchMove = (event: TouchEvent) => {
    if (lastTouchY === 0) { // no touch start event yet
      handleTouchStart(event);
      return;
    }

    const currentY = event.touches[0].clientY;
    const deltaY = lastTouchY - currentY;

    if (deltaY === 0) return; // no movement

    const currentTime = Date.now();
    const timeDelta = Math.max(10, currentTime - lastTouchTime);

    // limit extreme values
    const clampedDeltaY = Math.max(-100, Math.min(100, deltaY));

    // calculate touch velocity with limits
    touchVelocity = (clampedDeltaY / timeDelta) * 200;
    touchVelocity = Math.max(-2000, Math.min(2000, touchVelocity));

    // if clampedDeltaX - right swipe = zoom in, left swipe = zoom out
    // if clampedDeltaY - up swipe = zoom out, down swipe = zoom in
    // if -clampedDeltaY - up swipe = zoom in, down swipe = zoom out
    processInput(-clampedDeltaY, touchSensitivity);

    lastTouchY = currentY;
    lastTouchTime = currentTime;
    event.preventDefault();
  };

  const handleTouchEnd = (event: TouchEvent) => {
    // end of touch event - calculate final velocity
    if (Math.abs(touchVelocity) > 20 && Math.abs(touchVelocity) < 2000) {
      const limitedVelocity = Math.max(-500, Math.min(500, touchVelocity));
      processInput(limitedVelocity * 0.5, touchSensitivity);
    }

    touchVelocity = 0;
    event.preventDefault();
  };

  // set up the animation immediately
  timeline.pause();
  timeline.progress(initialJump); // for backwards animation (start backwards)

  window.addEventListener('wheel', handleWheel, { passive: false });
  window.addEventListener('touchstart', handleTouchStart, { passive: false });
  window.addEventListener('touchmove', handleTouchMove, { passive: false });
  window.addEventListener('touchend', handleTouchEnd, { passive: false });

  const animFrameId = requestAnimationFrame(smoothAnimationLoop);

  return {
    current: animState,
    cleanup: () => {
      window.removeEventListener('wheel', handleWheel);
      window.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleTouchEnd);
      cancelAnimationFrame(animFrameId);
      animState.active = false;
    }
  };
}