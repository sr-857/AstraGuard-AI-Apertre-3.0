import { useEffect, useState } from "react";

// WebGL enabled check. For example Safari browser has WebGL1.0 enabled by default and we can't work with that
export function useWebGL2Enabled() {
    const [isWebGL2Enabled, setIsWebGL2Enabled] = useState<boolean | null>(false);

    useEffect(() => {
        const detectWebGL2 = () => {
            try {
                const canvas = document.createElement("canvas");
                const gl2 = canvas.getContext("webgl2");
                if (gl2) {
                    const version = gl2.getParameter(gl2.VERSION);
                    console.log('WebGL version:', version);
                    return true;
                }
                console.log('WebGL 2.0 not enabled.');
                return false;
            } catch (e) {
                console.error('Error detecting WebGL:', e);
                return false;
            }
        };

        setIsWebGL2Enabled(detectWebGL2());
    }, []);

    return isWebGL2Enabled;
}