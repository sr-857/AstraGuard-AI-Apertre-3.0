import { useEffect, useState } from 'react';
import { useMobile } from '../contexts/MobileContext';
import styles from './MobileOrientationWarning.module.css';

const MobileOrientationWarning = () => {
  const { isMobile } = useMobile();
  const [isPortrait, setIsPortrait] = useState(false);

  // check device orientation for mobile devices
  useEffect(() => {
    if (!isMobile) return;

    const checkOrientation = () => {
      setIsPortrait(window.innerHeight > window.innerWidth);
    };

    // initial check
    checkOrientation();

    // listen for changes
    window.addEventListener('resize', checkOrientation);
    window.addEventListener('orientationchange', checkOrientation);

    return () => { // cleanup
      window.removeEventListener('resize', checkOrientation);
      window.removeEventListener('orientationchange', checkOrientation);
    };
  }, [isMobile]);

  // only show on mobile in portrait mode
  if (!isMobile || !isPortrait) return null;

  return (
    <div className={styles['orientation-warning']}>
      <div className={styles['rotating-container']}>
        <div className={styles['rotating-phone']}></div>
      </div>
      <div className={styles.message}>Please rotate your device</div>
      <div className={styles['sub-message']}>for better cosmic journey experience</div>
      <div className={styles['desktop-note']}>for the best experience, visit on a computer</div>
    </div>
  );
};

export default MobileOrientationWarning;