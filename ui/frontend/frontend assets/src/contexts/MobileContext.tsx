import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface MobileContextType {
  isMobile: boolean;
  isIOS: boolean;
}

const MobileContext = createContext<MobileContextType | undefined>(undefined);

export const MobileProvider: React.FC<{
  children: ReactNode;
}> = ({ children }) => {
  const [isMobile, setIsMobile] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    // determine if the device is mobile and IOS
    const checkDevice = () => {
      // mobile detection 
      const byTouchPoints = 'ontouchstart' in window && navigator.maxTouchPoints > 0; // or "> 2"
      const byUserAgent = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
      const byScreenSize = window.innerWidth <= 768; // common mobile breakpoint

      // iOS detection
      const isIOSUserAgent = /iPad|iPhone|iPod/.test(navigator.userAgent);
      const isIOSPlatform = navigator.platform && /iPad|iPhone|iPod/.test(navigator.platform);
      const isIOSVendor = navigator.vendor && navigator.vendor.includes("Apple");
      const isIPadModern =
        navigator.maxTouchPoints > 1 &&
        /Macintosh/.test(navigator.userAgent) &&
        !(/Windows NT/.test(navigator.userAgent));


      setIsMobile(byTouchPoints || byUserAgent || byScreenSize);
      setIsIOS(isIOSUserAgent || isIOSPlatform || (isIOSVendor && byTouchPoints) || isIPadModern);
    };

    checkDevice();
    window.addEventListener('resize', checkDevice);

    return () => window.removeEventListener('resize', checkDevice);
  }, []);

  return (
    <MobileContext.Provider value={{ isMobile, isIOS }}>
      {children}
    </MobileContext.Provider>
  );
};

// hook to use the mobile context
export const useMobile = (): MobileContextType => {
  const context = useContext(MobileContext);

  if (context === undefined) {
    throw new Error('useMobile must be used within a MobileProvider');
  }

  return context;
};