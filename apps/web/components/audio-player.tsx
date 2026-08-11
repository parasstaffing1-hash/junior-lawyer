"use client";

import { useState, useRef, useEffect } from "react";
import { Play, Pause, SkipBack, SkipForward, Volume2, X } from "lucide-react";

interface AudioPlayerProps {
  url?: string;
  title?: string;
  subtitle?: string;
  onClose?: () => void;
}

export function AudioPlayer({ 
  url = "/demo.mp3", 
  title = "Section 73: Compensation for loss...", 
  subtitle = "The Indian Contract Act, 1872",
  onClose
}: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    // In a real implementation, we would load the audio file here
    // For demo, we'll just simulate progress if playing
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 100) {
            setIsPlaying(false);
            return 0;
          }
          return prev + 1;
        });
      }, 500);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  const togglePlay = () => setIsPlaying(!isPlaying);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 shadow-lg px-4 py-3 sm:px-6">
      <div className="flex items-center justify-between max-w-screen-xl mx-auto">
        
        {/* Track Info */}
        <div className="flex items-center gap-4 w-1/3 min-w-0">
          <div className="h-12 w-12 bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400 rounded flex items-center justify-center shrink-0">
            <Volume2 className="h-6 w-6" />
          </div>
          <div className="truncate">
            <h4 className="font-semibold text-sm truncate">{title}</h4>
            <p className="text-xs text-gray-500 truncate">{subtitle}</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-col items-center w-1/3 max-w-md">
          <div className="flex items-center gap-6 mb-1">
            <button className="text-gray-500 hover:text-gray-900 dark:hover:text-white transition">
              <SkipBack className="h-5 w-5" />
            </button>
            <button 
              onClick={togglePlay}
              className="h-10 w-10 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center transition shadow-sm"
            >
              {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
            </button>
            <button className="text-gray-500 hover:text-gray-900 dark:hover:text-white transition">
              <SkipForward className="h-5 w-5" />
            </button>
          </div>
          <div className="w-full flex items-center gap-2 text-xs text-gray-500 font-medium">
            <span>0:00</span>
            <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-indigo-500 transition-all duration-300 ease-linear" 
                style={{ width: `${progress}%` }}
              />
            </div>
            <span>2:45</span>
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center justify-end gap-4 w-1/3">
          <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 font-semibold text-sm">
            <span>KanoonFM</span>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1">
              <X className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
