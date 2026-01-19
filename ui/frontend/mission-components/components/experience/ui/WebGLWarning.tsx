import { useEffect, useState } from 'react';
import styles from './WebGLWarning.module.css';


const WebGLWarning = () => {
  const [browserType, setBrowserType] = useState<'safari' | 'other' | null>(null);

  // hide initial loader as soon as WebGL warning is shown
  useEffect(() => {
    const initialLoader = document.getElementById('initial-loader');
    if (initialLoader) {
      initialLoader.style.display = 'none';
    }
  }, []);

  // browser detection
  useEffect(() => {
    const ua = navigator.userAgent.toLowerCase();
    if (ua.indexOf('safari') !== -1 && ua.indexOf('chrome') === -1) {
      setBrowserType('safari');
    } else {
      setBrowserType('other');
    }
  }, []);

  return (
    <div className={styles.container}>
      <div className={styles.stars}></div>

      <div className={styles.content}>
        <div className={styles.icon}>
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5" />
            <path d="M12 7V13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="12" cy="16" r="1" fill="currentColor" />
          </svg>
        </div>

        <h2 className={styles.heading}>WebGL Not Available</h2>

        {browserType === 'safari' ? (
          <div className={styles.instructions}>
            <p className={styles.text}>Enable WebGL2.0 in Safari settings:</p>
            <ol className={styles.orderedList}>
              <li className={styles.listItem}>Open Safari Preferences</li>
              <li className={styles.listItem}>Go to Advanced tab</li>
              <li className={styles.listItem}>Enable "Show Developer menu"</li>
              <li className={styles.listItem}>From Developer menu, enable WebGL (in Experimental settings)</li>
            </ol>
            <div className={styles.alternative}>
              <p className={styles.text}>Or use a different browser.</p>
            </div>
          </div>
        ) : (
          <div className={styles.instructions}>
            <p className={styles.text}>Your browser doesn't support WebGL2.0 or it's disabled.</p>
            <ul className={styles.list}>
              <li className={styles.listItem}>Update your graphics drivers</li>
              <li className={styles.listItem}>Enable hardware acceleration</li>
              <li className={styles.listItem}>Try Chrome or Firefox</li>
            </ul>
            <a href="https://get.webgl.org" target="_blank" rel="noopener noreferrer" className={styles.link}>
              Test WebGL Support
            </a>
          </div>
        )}

        <button onClick={() => window.location.reload()} className={styles.button}>
          <span className={styles.buttonText}>Try Again</span>
        </button>
      </div>
    </div>
  );
};

export default WebGLWarning;