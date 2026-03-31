import { useState, useEffect, useRef } from 'react';
import { formatTime } from '@/utils/formatTime';
import { type TranscriptSegment } from '@/types/transcript';

interface AudioPlayerProps {
  src: string;
  title?: string;
  segments?: TranscriptSegment[];
  onTimeUpdate?: (time: number) => void;
}

export const AudioPlayer = ({ src, title, segments, onTimeUpdate }: AudioPlayerProps) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateTime = () => {
      setCurrentTime(audio.currentTime);
      onTimeUpdate?.(audio.currentTime);
    };

    const updateDuration = () => setDuration(audio.duration);
    const togglePlaying = () => setIsPlaying(!audio.paused);

    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('play', togglePlaying);
    audio.addEventListener('pause', togglePlaying);

    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
      audio.removeEventListener('play', togglePlaying);
      audio.removeEventListener('pause', togglePlaying);
    };
  }, [onTimeUpdate]);

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
    }
  };

  return (
    <div className="space-y-3">
      {title && <p className="font-medium text-gray-700">{title}</p>}
      
      <audio ref={audioRef} src={src} className="hidden" />
      
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          className="p-2 rounded-full bg-primary-600 text-white hover:bg-primary-700 transition-colors"
        >
          {isPlaying ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>
        
        <div className="flex-1 flex items-center gap-2">
          <span className="text-xs text-gray-500 w-10">{formatTime(currentTime)}</span>
          <input
            type="range"
            min={0}
            max={duration || 100}
            value={currentTime}
            onChange={handleSeek}
            className="flex-1 accent-primary-600"
          />
          <span className="text-xs text-gray-500 w-10 text-right">{formatTime(duration)}</span>
        </div>
      </div>

      {/* Segments timeline */}
      {segments && segments.length > 0 && (
        <div className="relative h-8 bg-gray-100 rounded overflow-hidden">
          {segments.map((seg, idx) => {
            const left = (seg.start / duration) * 100;
            const width = ((seg.stop - seg.start) / duration) * 100;
            return (
              <div
                key={idx}
                className="absolute top-0 h-full bg-primary-200 border-l border-primary-400"
                style={{ left: `${left}%`, width: `${width}%` }}
                title={`${seg.Speaker}: ${seg.Text.slice(0, 50)}...`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};