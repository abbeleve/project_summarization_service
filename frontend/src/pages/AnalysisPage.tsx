import { useParams, useNavigate } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { SummaryCard } from '@/components/analysis/SummaryCard';
import { SpeakerDistributionChart } from '@/components/analysis/SpeakerDistributionChart';
import { TranscriptSegment } from '@/components/analysis/TranscriptSegment';
import { MeetingChat } from '@/components/analysis/MeetingChat';
import { AudioPlayer } from '@/components/audio/AudioPlayer';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { type TranscriptSegment as TranscriptSegmentType } from '@/types/transcript';

export const AnalysisPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getTranscript } = useTranscripts();
  const { data: transcript, isLoading, error } = getTranscript(id || '');

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
        <div className="flex gap-2">
          <Button variant="secondary" size="sm">
            📥 Скачать JSON
          </Button>
          <Button variant="secondary" size="sm">
            📋 Скачать отчёт
          </Button>
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
            <Card className="p-4">
              <AudioPlayer 
                src={audioUrl}
                segments={segments}
              />
            </Card>
          )}

          {/* Диаграмма распределения спикеров */}
          {segments.length > 0 && (
            <SpeakerDistributionChart segments={segments} />
          )}

          {/* Полная транскрипция */}
          <Card className="p-4">
            <h4 className="font-semibold text-gray-900 mb-4">📝 Детальная транскрипция</h4>
            <div className="space-y-3 max-h-[600px] overflow-y-auto">
              {segments.map((seg, idx) => (
                <TranscriptSegment
                  key={idx}
                  speaker={seg.Speaker}
                  text={seg.Text}
                  startTime={seg.start}
                  endTime={seg.stop}
                />
              ))}
            </div>
          </Card>
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