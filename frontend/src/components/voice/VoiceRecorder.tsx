import { useState, useRef, useCallback, useEffect } from 'react';
import { voiceApi } from '@/api/voice';
import { clsx } from 'clsx';

type RecorderState = 'idle' | 'recording' | 'recorded' | 'uploading' | 'success' | 'error';

interface VoiceRecorderProps {
  hasExistingProfile: boolean;
  onProfileChange: () => void;
}

export const VoiceRecorder = ({ hasExistingProfile, onProfileChange }: VoiceRecorderProps) => {
  const [state, setState] = useState<RecorderState>('idle');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const startRecording = useCallback(async () => {
    setError(null);
    setAudioUrl(null);
    setAudioBlob(null);
    setRecordingTime(0);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      });

      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());

        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setAudioBlob(blob);
        setDuration(blob.size / (16_000 * 2) * 1000); // rough estimate
        setState('recorded');
      };

      mediaRecorder.start(100); // collect data every 100ms
      setState('recording');

      // Timer
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => {
          if (prev >= 30) {
            stopRecording();
            return 30;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err) {
      const message =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Доступ к микрофону запрещён. Разрешите доступ в настройках браузера.'
          : 'Не удалось запустить запись. Проверьте микрофон.';
      setError(message);
      setState('idle');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const uploadRecording = useCallback(async () => {
    if (!audioBlob) return;

    setState('uploading');
    setError(null);

    try {
      // Convert webm to wav-compatible format for the backend
      const response = await voiceApi.enroll(audioBlob);
      if (response.has_profile) {
        setState('success');
        onProfileChange();
      } else {
        throw new Error('Profile was not created');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка при загрузке';
      setError(message);
      setState('recorded');
    }
  }, [audioBlob, onProfileChange]);

  const resetRecording = useCallback(() => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setAudioBlob(null);
    setState('idle');
    setDuration(0);
    setRecordingTime(0);
    setError(null);
  }, [audioUrl]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-4">
      {/* Status info */}
      {hasExistingProfile && state === 'idle' && (
        <p className="text-sm text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
          <span>✓</span>
          Голосовой профиль активен. Новая запись заменит существующий.
        </p>
      )}

      {/* Recording indicator */}
      {state === 'recording' && (
        <div className="flex items-center gap-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
          <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
          <div className="flex-1">
            <div className="h-2 bg-red-100 dark:bg-red-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-500 rounded-full transition-all duration-1000"
                style={{ width: `${(recordingTime / 30) * 100}%` }}
              />
            </div>
          </div>
          <span className="text-sm font-mono text-red-600 dark:text-red-400">
            {formatTime(recordingTime)} / 0:30
          </span>
          <button
            onClick={stopRecording}
            className="px-3 py-1 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
          >
            Стоп
          </button>
        </div>
      )}

      {/* Recorded audio preview + action buttons */}
      {state === 'recorded' && audioUrl && (
        <div className="space-y-3 p-4 bg-gray-50 dark:bg-dark-base-800/50 rounded-lg border border-gray-200 dark:border-dark-base-700">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Запись готова
            </span>
            <span className="text-xs text-gray-500">
              ~{Math.round(duration / 1000)} сек
            </span>
          </div>

          <audio
            ref={audioRef}
            src={audioUrl}
            controls
            className="w-full h-10"
          />

          <div className="flex gap-2">
            <button
              onClick={resetRecording}
              className="flex-1 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-base-700 border border-gray-300 dark:border-dark-base-600 rounded-lg hover:bg-gray-50 dark:hover:bg-dark-base-600 transition-colors"
            >
              Перезаписать
            </button>
            <button
              onClick={uploadRecording}
              disabled={state === 'uploading'}
              className="flex-1 px-3 py-2 text-sm font-medium text-white bg-violet-600 hover:bg-violet-700 disabled:bg-violet-400 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {state === 'uploading' ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Загрузка...
                </>
              ) : (
                'Сохранить голос'
              )}
            </button>
          </div>
        </div>
      )}

      {/* Success message */}
      {state === 'success' && (
        <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
          <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
            ✓ Голосовой профиль успешно сохранён
          </p>
          <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">
            Теперь система сможет идентифицировать вас как спикера в расшифровках встреч.
          </p>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {/* Idle state - start recording button */}
      {state === 'idle' && (
        <div className="flex flex-col items-center gap-3 p-6 bg-gray-50 dark:bg-dark-base-800/30 rounded-lg border-2 border-dashed border-gray-300 dark:border-dark-base-600">
          <div className="w-16 h-16 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
            <span className="text-3xl">🎤</span>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 text-center max-w-sm">
            Запишите 10–30 секунд вашей речи для создания голосового профиля.
            <br />
            Говорите чётко, в тишине.
          </p>
          <button
            onClick={startRecording}
            className="px-6 py-3 text-sm font-medium text-white bg-violet-600 hover:bg-violet-700 rounded-xl transition-colors shadow-lg shadow-violet-200 dark:shadow-violet-900/30 flex items-center gap-2"
          >
            <span>●</span>
            Начать запись
          </button>
        </div>
      )}
    </div>
  );
};