import { useEffect, useState } from 'react';
import styles from './NavigationHint.module.css';
import { useMobile } from '../contexts/MobileContext';
const touchHandIcon = '/assets/icons/navigation_hint/touch_hand.svg';
const zoomInIcon = '/assets/icons/navigation_hint/zoom_in.svg';
const zoomOutIcon = '/assets/icons/navigation_hint/zoom_out.svg';


const NavigationHint = () => {
  const { isMobile } = useMobile();
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    // hide indicator after user has interacted
    const hideOnInteraction = (event: TouchEvent | WheelEvent | MouseEvent) => {
      if (isMobile && event.type === 'touchstart' ||
        !isMobile && (event.type === 'wheel' ||
          event.type === 'mousedown')) {
        setVisible(false);
      }
    };

    // add event listeners based on device
    if (isMobile) {
      window.addEventListener('touchstart', hideOnInteraction);
    } else {
      window.addEventListener('wheel', hideOnInteraction);
      window.addEventListener('mousedown', hideOnInteraction);
    }

    return () => {
      window.removeEventListener('touchstart', hideOnInteraction);
      window.removeEventListener('wheel', hideOnInteraction);
      window.removeEventListener('mousedown', hideOnInteraction);
    };
  }, [isMobile]);

  if (!visible) return null;

  return (
    <div className={`${styles['navigation-hint']} ${isMobile ? styles['mobile'] : styles['desktop']}`}>
      {isMobile ? (
        // mobile swipe hint
        <>
          <div className={`${styles['gesture-container']} ${styles['mobile']}`}>
            <div className={styles['swipe-container']}>
              <div className={`${styles['zoom-indicator']} ${styles['top']}`}>
                <img src={zoomInIcon} alt="Zoom In" className={styles['zoom-icon']} />
              </div>

              <div className={styles['swipe-indicator']}>
                <div className={styles['swipe-track']}></div>
                <img src={touchHandIcon} alt="Touch and swipe" className={styles['touch-hand']} />
              </div>

              <div className={`${styles['zoom-indicator']} ${styles['bottom']}`}>
                <img src={zoomOutIcon} alt="Zoom Out" className={styles['zoom-icon']} />
              </div>
            </div>
          </div>
          <p className={styles['hint-title']}>Swipe to Navigate</p>
        </>
      ) : (
        // desktop scroll hint
        <>
          <div className={`${styles['gesture-container']} ${styles['desktop']}`}>
            <div className={styles['scroll-indicator']}>
              <div className={styles['zoom-controls']}>
                <div className={`${styles['scroll-action']} ${styles['vertical']}`}>
                  <img src={zoomInIcon} alt="Zoom In" className={styles['zoom-icon']} />
                </div>

                <div className={`${styles['scroll-action']} ${styles['vertical']}`}>
                  <img src={zoomOutIcon} alt="Zoom Out" className={styles['zoom-icon']} />
                </div>
              </div>

              <div className={styles['mouse-body']}>
                <div className={styles['mouse-wheel']}></div>
              </div>
            </div>
          </div>
          <p className={styles['hint-title']}>Scroll to Navigate</p>
        </>
      )}
    </div>
  );
};

export default NavigationHint;