import React, { useRef, useEffect, useState, useCallback } from 'react';
import { CameraMode, Point } from '../types';
import { analyzeFrame } from '../services/geminiService';
import { ArrowPathIcon, CameraIcon, EyeIcon, ExclamationTriangleIcon } from '@heroicons/react/24/solid';

const FRAME_RATE = 30;

const CameraInterface: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mode, setMode] = useState<CameraMode>(CameraMode.AUTO);
  const [points, setPoints] = useState<Point[]>([]);
  const [fps, setFps] = useState(0);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const lastTimeRef = useRef<number>(performance.now());
  const frameIdRef = useRef<number>(0);

  // Initialize Camera
  useEffect(() => {
    const startCamera = async () => {
      try {
        setCameraError(null);
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { width: 640, height: 480 } 
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          // Explicitly play to ensure mobile/safari compatibility
          await videoRef.current.play();
        }
      } catch (err) {
        console.error("Error accessing webcam:", err);
        setCameraError("Unable to access camera. Please allow permissions.");
      }
    };
    startCamera();
    
    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const stream = videoRef.current?.srcObject as MediaStream;
      stream?.getTracks().forEach(track => track.stop());
    };
  }, []);

  // Drawing Loop (Simulating OpenCV processing)
  const draw = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // Check if video is ready (HAVE_CURRENT_DATA = 2, HAVE_ENOUGH_DATA = 4)
    if (!ctx || video.readyState < 2) {
      frameIdRef.current = requestAnimationFrame(draw);
      return;
    }

    // FPS Calculation
    const now = performance.now();
    const dt = now - lastTimeRef.current;
    if (dt >= 1000 / FRAME_RATE) {
      const currentFps = 1000 / dt;
      setFps(prev => Math.round(prev * 0.9 + currentFps * 0.1));
      lastTimeRef.current = now;

      // Draw Video Frame
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // --- SIMULATED CV OVERLAY ---
      
      // 1. Overlay Mask (Green tint)
      // Removed mock center blob for Auto Mode as requested.
      if (mode === CameraMode.INTERACTIVE && points.length > 0) {
        // Mock Interactive: Blobs around points
        ctx.save();
        ctx.globalAlpha = 0.4;
        ctx.fillStyle = '#4ade80';
        for (const p of points) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 60, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }

      // 2. Draw Points (Interactive Mode)
      if (mode === CameraMode.INTERACTIVE) {
        for (const p of points) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
          ctx.fillStyle = '#ef4444'; // Red
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }

      // 3. HUD (Heads Up Display)
      ctx.font = 'bold 20px "JetBrains Mono"';
      ctx.fillStyle = '#4ade80'; // Green text
      ctx.fillText(`FPS: ${fps}`, 20, 40);
      
      ctx.fillStyle = '#38bdf8'; // Blue text
      ctx.fillText(`MODE: ${mode}`, 20, 70);

      // Crosshair
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(canvas.width / 2, 0);
      ctx.lineTo(canvas.width / 2, canvas.height);
      ctx.moveTo(0, canvas.height / 2);
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    }

    frameIdRef.current = requestAnimationFrame(draw);
  }, [fps, mode, points]);

  useEffect(() => {
    frameIdRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameIdRef.current);
  }, [draw]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (mode !== CameraMode.INTERACTIVE) return;
    
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Scale coordinates to canvas resolution
    const scaleX = (canvasRef.current?.width || 1) / rect.width;
    const scaleY = (canvasRef.current?.height || 1) / rect.height;

    setPoints(prev => [...prev, { x: x * scaleX, y: y * scaleY, label: 1 }]);
  };

  const handleReset = () => setPoints([]);

  const handleAnalyze = async () => {
    if (!canvasRef.current) return;
    setIsAnalyzing(true);
    setAnalysis("Analyzing frame with Gemini Vision...");
    
    try {
      const dataUrl = canvasRef.current.toDataURL('image/png');
      const result = await analyzeFrame(dataUrl);
      setAnalysis(result);
    } catch (err) {
      setAnalysis("Failed to connect to AI service.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 w-full max-w-7xl mx-auto p-4">
      {/* Video Feed Section */}
      <div className="flex-1 relative bg-black rounded-xl overflow-hidden shadow-2xl border border-gray-800 aspect-video lg:aspect-auto flex items-center justify-center">
        
        {/* Error State */}
        {cameraError && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-gray-900/90 text-center p-6">
            <ExclamationTriangleIcon className="w-16 h-16 text-yellow-500 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">Camera Access Error</h3>
            <p className="text-gray-400 max-w-md">{cameraError}</p>
          </div>
        )}

        {/* Video Element (Hidden from view but kept in DOM for processing) */}
        {/* IMPORTANT: Do not use display:none or hidden class, as browsers stop decoding frames */}
        <video 
          ref={videoRef} 
          autoPlay 
          muted 
          playsInline 
          className="absolute inset-0 opacity-0 pointer-events-none w-full h-full object-cover" 
        />
        
        <canvas 
          ref={canvasRef}
          className="w-full h-full object-contain cursor-crosshair relative z-10"
          onClick={handleCanvasClick}
        />
        
        {/* Overlay Instructions */}
        {!cameraError && (
          <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end pointer-events-none z-20">
            <div className="bg-black/60 backdrop-blur-sm p-3 rounded-lg text-xs font-mono text-gray-300">
              <p>[1] Auto Mode | [2] Interactive Mode</p>
              <p>[Click] Add Point | [R] Reset</p>
            </div>
          </div>
        )}
      </div>

      {/* Controls & Analysis Panel */}
      <div className="w-full lg:w-96 flex flex-col gap-4">
        
        {/* Control Deck */}
        <div className="bg-cv-panel p-6 rounded-xl border border-gray-700">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <span className="w-2 h-8 bg-cv-accent rounded-full"></span>
            Control Deck
          </h2>
          
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <button 
                onClick={() => setMode(CameraMode.AUTO)}
                className={`p-3 rounded-lg font-mono text-sm transition-all ${mode === CameraMode.AUTO ? 'bg-cv-accent text-black font-bold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
              >
                AUTO MODE
              </button>
              <button 
                onClick={() => setMode(CameraMode.INTERACTIVE)}
                className={`p-3 rounded-lg font-mono text-sm transition-all ${mode === CameraMode.INTERACTIVE ? 'bg-cv-accent text-black font-bold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
              >
                INTERACTIVE
              </button>
            </div>

            <div className="flex gap-2">
              <button 
                onClick={handleReset}
                disabled={points.length === 0}
                className="flex-1 flex items-center justify-center gap-2 p-3 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white rounded-lg transition-colors font-mono text-sm"
              >
                <ArrowPathIcon className="w-4 h-4" />
                RESET POINTS ({points.length})
              </button>
            </div>
            
            <button 
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              className="w-full flex items-center justify-center gap-2 p-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold rounded-lg shadow-lg transition-all"
            >
              {isAnalyzing ? (
                <span className="animate-pulse">ANALYZING...</span>
              ) : (
                <>
                  <EyeIcon className="w-5 h-5" />
                  ANALYZE WITH GEMINI
                </>
              )}
            </button>
          </div>
        </div>

        {/* Analysis Log */}
        <div className="flex-1 bg-cv-panel p-6 rounded-xl border border-gray-700 flex flex-col min-h-[200px]">
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">System Log</h3>
          <div className="flex-1 bg-black/50 rounded-lg p-4 font-mono text-sm text-green-400 overflow-y-auto max-h-[300px] border border-gray-800">
            {analysis ? (
               <div className="whitespace-pre-wrap leading-relaxed">
                 <span className="text-gray-500">[{new Date().toLocaleTimeString()}]</span> {analysis}
               </div>
            ) : (
              <span className="text-gray-600 italic">Waiting for analysis request...</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CameraInterface;