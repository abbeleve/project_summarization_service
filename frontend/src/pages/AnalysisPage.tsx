import { useParams, useNavigate } from 'react-router-dom';
import { useRef, useState } from 'react';
import { useTranscripts } from '@/hooks/useTranscripts';
import { transcriptsApi } from '@/api/transcripts';
import { SummaryCard } from '@/components/analysis/SummaryCard';
import { SpeakerDistributionChart } from '@/components/analysis/SpeakerDistributionChart';
import { TranscriptSegment } from '@/components/analysis/TranscriptSegment';
import { MeetingChat } from '@/components/analysis/MeetingChat';
import { AudioPlayer } from '@/components/audio/AudioPlayer';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Button } from '@/components/ui/Button';
import { type TranscriptSegment as TranscriptSegmentType } from '@/types/transcript';

export const AnalysisPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getTranscript } = useTranscripts();
  const { data: transcript, isLoading, error, refetch } = getTranscript(id || '');
  const transcriptContainerRef = useRef<HTMLDivElement>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Функция для прокрутки к нужному сегменту
  const handleSegmentClick = (segment: TranscriptSegmentType) => {
    if (transcriptContainerRef.current) {
      // Находим элемент с нужным startTime в data-атрибуте
      const elements = transcriptContainerRef.current.querySelectorAll('[data-start-time]');
      let targetElement: Element | null = null;

      // Ищем ближайший сегмент по времени
      for (const el of elements) {
        const startTime = parseFloat(el.getAttribute('data-start-time') || '0');
        if (Math.abs(startTime - segment.start) < 0.1) {
          targetElement = el;
          break;
        }
      }

      if (targetElement) {
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Подсветим элемент
        targetElement.classList.add('ring-2', 'ring-primary-500', 'ring-offset-2');
        setTimeout(() => {
          targetElement?.classList.remove('ring-2', 'ring-primary-500', 'ring-offset-2');
        }, 2000);
      }
    }
  };

  // Переименование транскрипции
  const handleRename = async () => {
    if (!id || !editTitle.trim()) return;
    
    setIsSaving(true);
    try {
      await transcriptsApi.rename(id, editTitle.trim());
      await refetch();
      setIsEditing(false);
    } catch (err) {
      console.error('Ошибка переименования:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const startEditing = () => {
    setEditTitle(transcript?.title || '');
    setIsEditing(true);
  };

  if (!id) {
    return (
      <ErrorMessage 
        message="ID транскрипции не указан" 
        onRetry={() => navigate('/')}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner text="Загрузка транскрипции..." size={'sm'} />
      </div>
    );
  }

  if (error || !transcript) {
    return (
      <ErrorMessage 
        message="Транскрипция не найдена" 
        onRetry={() => navigate('/')}
      />
    );
  }

  const segments: TranscriptSegmentType[] = transcript.segments || 
    (transcript.parts || []).map(p => ({
      Speaker: p.text.split(':')[0] || 'UNKNOWN',
      Text: p.text.split(':').slice(1).join(':').trim(),
      start: p.start_time / 1000,
      stop: p.end_time / 1000
    }));

  // Конвертация Blob в URL для аудио (если есть)
  const audioUrl = transcript.audio_blob 
    ? URL.createObjectURL(transcript.audio_blob) 
    : '';

  return (
    <div className="space-y-6">
      {/* Шапка с кнопками навигации */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => navigate('/')}>
          ← Назад
        </Button>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRename();
                  if (e.key === 'Escape') setIsEditing(false);
                }}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:outline-none"
                placeholder="Новое название"
                autoFocus
              />
              <Button
                size="sm"
                onClick={handleRename}
                disabled={isSaving || !editTitle.trim()}
              >
                {isSaving ? '...' : '💾'}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setIsEditing(false)}
              >
                ✕
              </Button>
            </div>
          ) : (
            <>
              <Button variant="secondary" size="sm" onClick={startEditing}>
                ✏️ Переименовать
              </Button>
              <Button variant="secondary" size="sm">
                📥 Скачать JSON
              </Button>
              <Button variant="secondary" size="sm">
                📋 Скачать отчёт
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Карточка резюме */}
      {transcript.summary && (
        <SummaryCard
          title={transcript.title}
          summary={transcript.summary}
          keyPoints={transcript.key_points || []}
          meetingType={transcript.meeting_type}
        />
      )}

      {/* Двухколоночная раскладка */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Левая колонка - транскрипция */}
        <div className="lg:col-span-2 space-y-6">
          {/* Аудио плеер */}
          {segments.length > 0 && audioUrl && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <AudioPlayer
                src={audioUrl}
                segments={segments}
              />
            </div>
          )}

          {/* Диаграмма распределения спикеров */}
          {segments.length > 0 && (
            <SpeakerDistributionChart 
              segments={segments}
              onSegmentClick={handleSegmentClick}
            />
          )}

          {/* Полная транскрипция */}
          <div
            ref={transcriptContainerRef}
            className="bg-gradient-to-r from-slate-50 to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl p-5 border border-gray-200 dark:border-gray-700"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-400 to-gray-500 flex items-center justify-center shadow-md">
                <span className="text-lg">📝</span>
              </div>
              <h4 className="text-lg font-bold text-gray-900 dark:text-white">Детальная транскрипция</h4>
            </div>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
              {segments.map((seg, idx) => (
                <div key={idx} data-start-time={seg.start}>
                  <TranscriptSegment
                    speaker={seg.Speaker}
                    text={seg.Text}
                    startTime={seg.start}
                    endTime={seg.stop}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Правая колонка - чат */}
        <div className="lg:col-span-1">
          <MeetingChat
            transcriptId={id}
            transcriptText={transcript.original_text}
          />
        </div>
      </div>
    </div>
  );
};