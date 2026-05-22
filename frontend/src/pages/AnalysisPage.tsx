import { useParams, useNavigate } from 'react-router-dom';
import { useRef, useState, useCallback, useEffect } from 'react';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useAnnotations } from '@/hooks/useAnnotations';
import { transcriptsApi } from '@/api/transcripts';
import { voiceApi, usersApi } from '@/api/voice';
import { getDominantColorsMap } from '@/utils/dominantColor';
import { SummaryCard } from '@/components/analysis/SummaryCard';
import { SpeakerDistributionChart } from '@/components/analysis/SpeakerDistributionChart';
import { TranscriptSegment } from '@/components/analysis/TranscriptSegment';
import { AnnotatedText } from '@/components/analysis/AnnotatedText';
import { MeetingChat } from '@/components/analysis/MeetingChat';
import { AudioPlayer } from '@/components/audio/AudioPlayer';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Button } from '@/components/ui/Button';
import { type TranscriptSegment as TranscriptSegmentType } from '@/types/transcript';
import { type Annotation } from '@/api/transcripts';
import { getSpeakerColor } from '@/utils/speakerColors';

export const AnalysisPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getTranscript } = useTranscripts();
  const { data: transcript, isLoading, error, refetch } = getTranscript(id || '');
  const { annotations, createAnnotation, deleteAnnotation } = useAnnotations(id || '');
  const transcriptContainerRef = useRef<HTMLDivElement>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [selectedText, setSelectedText] = useState<{
    text: string;
    partId: string;
    startChar: number;
    endChar: number;
  } | null>(null);
  const [showAnnotationPopup, setShowAnnotationPopup] = useState(false);
  const [selectedColor, setSelectedColor] = useState('yellow');
  const [annotationNote, setAnnotationNote] = useState('');
  const [showAnnotationsPanel, setShowAnnotationsPanel] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const ANNOTATION_COLORS = [
    { name: 'yellow', bg: 'bg-yellow-200 dark:bg-yellow-900/40', label: 'Жёлтый' },
    { name: 'green', bg: 'bg-green-200 dark:bg-green-900/40', label: 'Зелёный' },
    { name: 'blue', bg: 'bg-blue-200 dark:bg-blue-900/40', label: 'Синий' },
    { name: 'pink', bg: 'bg-pink-200 dark:bg-pink-900/40', label: 'Розовый' },
    { name: 'purple', bg: 'bg-purple-200 dark:bg-purple-900/40', label: 'Фиолетовый' },
  ];

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

  // Загружаем enrolled speakers: строим map user_id → { avatarUrl, fullName }
  const [speakerInfoMap, setSpeakerInfoMap] = useState<Record<string, { avatarUrl: string; fullName: string }>>({});
  const [dominantColors, setDominantColors] = useState<Record<string, string>>({});
  useEffect(() => {
    voiceApi.getEnrolledSpeakers().then(async (data) => {
      const map: Record<string, { avatarUrl: string; fullName: string }> = {};
      for (const s of data.speakers) {
        if (s.user_id) {
          map[s.user_id] = {
            avatarUrl: `http://localhost:8000/users/me/avatar?user_id=${s.user_id}`,
            fullName: s.full_name,
          };
        }
      }
      setSpeakerInfoMap(map);

      // Извлекаем доминантный цвет из аватарок
      const avatarUrlMap: Record<string, string> = {};
      for (const [uid, info] of Object.entries(map)) {
        avatarUrlMap[uid] = info.avatarUrl;
      }
      const colors = await getDominantColorsMap(avatarUrlMap);
      setDominantColors(colors);
    }).catch(() => {});
  }, []);

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

  // Обработка выделения текста
  const handleTextSelection = useCallback(() => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.toString().trim()) {
      return;
    }

    const range = selection.getRangeAt(0);
    const container = range.commonAncestorContainer.parentElement?.closest('[data-part-id]');
    
    if (!container) return;

    const partId = container.getAttribute('data-part-id')!;
    
    // Находим элемент с текстом (p тег внутри TranscriptSegment)
    const textElement = container.querySelector('p');
    if (!textElement) return;
    
    // Получаем полный текст из элемента
    const fullText = textElement.textContent || '';
    const selectedText = selection.toString();
    
    // Находим позицию выделенного текста в полном тексте
    const startChar = fullText.indexOf(selectedText);
    if (startChar === -1) {
      console.warn('Не удалось найти позицию выделенного текста');
      return;
    }
    const endChar = startChar + selectedText.length;

    setSelectedText({
      text: selectedText,
      partId,
      startChar,
      endChar
    });
    setShowAnnotationPopup(true);
  }, []);

  // Создание аннотации
  const handleCreateAnnotation = async () => {
    if (!selectedText || !id) return;
    
    try {
      await createAnnotation({
        part_id: selectedText.partId,
        start_char: selectedText.startChar,
        end_char: selectedText.endChar,
        color: selectedColor,
        note: annotationNote || undefined
      });
      setShowAnnotationPopup(false);
      setSelectedText(null);
      setSelectedColor('yellow');
      setAnnotationNote('');
      window.getSelection()?.removeAllRanges();
      showToast('✅ Аннотация создана', 'success');
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Ошибка создания аннотации';
      if (err.response?.status === 409) {
        showToast('⚠️ Этот участок уже подчеркнут', 'error');
      } else {
        showToast('❌ ' + message, 'error');
      }
    }
  };

  // Прокрутка к аннотации
  const scrollToAnnotation = (annotation: Annotation) => {
    const element = transcriptContainerRef.current?.querySelector(`[data-part-id="${annotation.part_id}"]`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.classList.add('ring-2', 'ring-violet-500', 'ring-offset-2');
      setTimeout(() => {
        element.classList.remove('ring-2', 'ring-violet-500', 'ring-offset-2');
      }, 2000);
    }
  };

  // Удаление аннотации
  const handleDeleteAnnotation = async (annotationId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      await deleteAnnotation(annotationId);
      showToast('🗑️ Аннотация удалена', 'success');
    } catch (err) {
      console.error('Ошибка удаления аннотации:', err);
      showToast('❌ Ошибка удаления', 'error');
    }
  };

  // Клик по аннотации в тексте
  const handleAnnotationClick = (annotation: Annotation) => {
    // Открываем панель если закрыта
    setShowAnnotationsPanel(true);

    // Прокручиваем к нужной аннотации в панели
    setTimeout(() => {
      const panel = document.querySelector('.annotations-panel');
      if (panel) {
        const annotationElement = panel.querySelector(`[data-annotation-id="${annotation.id}"]`);
        if (annotationElement) {
          annotationElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
          annotationElement.classList.add('ring-2', 'ring-violet-500');
          setTimeout(() => {
            annotationElement.classList.remove('ring-2', 'ring-violet-500');
          }, 2000);
        }
      }
    }, 100);
  };

  // Аннотация всей реплики через флажок
  const handleCreateFullAnnotation = (partId: string, text: string) => {
    setSelectedText({
      text,
      partId,
      startChar: 0,
      endChar: text.length
    });
    setShowAnnotationPopup(true);
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

  const segments = (transcript.parts || []).map(p => {
    const speaker = p.text.split(':')[0] || 'UNKNOWN';
    let avatarUrl: string | null = null;
    let colorSeed: string | null = null;
    let dominantColor: string | null = null;

    // Если employee_id проставлен — берём аватарку и цвет по аккаунту
    if (p.employee_id && speakerInfoMap[p.employee_id]) {
      const info = speakerInfoMap[p.employee_id];
      avatarUrl = info.avatarUrl;
      colorSeed = p.employee_id;
      dominantColor = dominantColors[p.employee_id] || null;
    }

    return {
      Speaker: speaker,
      Text: p.text.split(':').slice(1).join(':').trim(),
      start: p.start_time / 1000,
      stop: p.end_time / 1000,
      partId: p.id,
      avatarUrl,
      colorSeed,
      dominantColor,
    };
  });

  // Конвертация Blob в URL для аудио (если есть)
  const audioUrl = transcript.audio_url || (transcript.audio_blob
    ? URL.createObjectURL(transcript.audio_blob)
    : '');

  return (
    <div className="space-y-6">
      {/* Шапка с кнопками навигации */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => navigate('/')}>
          ← Назад
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowAnnotationsPanel(!showAnnotationsPanel)}
            className="relative"
          >
            📌 Аннотации
            {annotations.length > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                {annotations.length}
              </span>
            )}
          </Button>
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
                className="px-3 py-1.5 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:outline-none"
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
          {/* Диаграмма распределения спикеров */}
          {segments.length > 0 && (
            <SpeakerDistributionChart
              segments={segments}
              onSegmentClick={handleSegmentClick}
            />
          )}

          {/* Аудио плеер — между графиками и детальной транскрипцией */}
          {segments.length > 0 && audioUrl && (
            <div className="bg-white dark:bg-dark-base-800 rounded-xl border border-gray-200 dark:border-dark-base-700 p-4 shadow-sm">
              <AudioPlayer
                src={audioUrl}
                segments={segments}
              />
            </div>
          )}

          {/* Полная транскрипция */}
          <div
            ref={transcriptContainerRef}
            onMouseUp={handleTextSelection}
            className="bg-gradient-to-r from-slate-50 to-gray-50 dark:from-dark-base-800 dark:to-dark-base-900 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-400 to-gray-500 flex items-center justify-center shadow-md">
                  <span className="text-lg">📝</span>
                </div>
                <h4 className="text-lg font-bold text-gray-900 dark:text-white">Детальная транскрипция</h4>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                💡 Выделите текст чтобы создать аннотацию
              </p>
            </div>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
              {segments.map((seg, idx) => (
                <div key={idx} data-start-time={seg.start}>
                  <TranscriptSegment
                    speaker={seg.Speaker}
                    text={seg.Text}
                    startTime={seg.start}
                    endTime={seg.stop}
                    partId={seg.partId}
                    avatarUrl={seg.avatarUrl}
                    colorSeed={seg.colorSeed}
                    dominantColor={seg.dominantColor}
                    annotations={annotations}
                    onAnnotationClick={handleAnnotationClick}
                    onCreateFullAnnotation={handleCreateFullAnnotation}
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

      {/* Popup для создания аннотации */}
      {showAnnotationPopup && selectedText && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-dark-base-800 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Создать аннотацию</h3>
            
            <div className="mb-4 p-3 bg-gray-50 dark:bg-dark-base-700 rounded-lg">
              <p className="text-sm text-gray-700 dark:text-gray-300 italic">
                "{selectedText.text}"
              </p>
            </div>

            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Выберите цвет:</p>
              <div className="flex gap-2">
                {ANNOTATION_COLORS.map((color) => (
                  <button
                    key={color.name}
                    onClick={() => setSelectedColor(color.name)}
                    className={`w-8 h-8 rounded-full ${color.bg} border-2 transition-all ${
                      selectedColor === color.name ? 'border-gray-900 dark:border-white scale-110' : 'border-transparent'
                    }`}
                    title={color.label}
                  />
                ))}
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Комментарий (необязательно):
              </label>
              <textarea
                value={annotationNote}
                onChange={(e) => setAnnotationNote(e.target.value)}
                placeholder="Напишите заметку к аннотации..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-violet-500 focus:outline-none resize-none text-sm"
              />
            </div>

            <div className="flex gap-2">
              <Button
                variant="primary"
                onClick={handleCreateAnnotation}
                className="flex-1"
              >
                ✓ Подчеркнуть
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setShowAnnotationPopup(false);
                  setSelectedText(null);
                  setSelectedColor('yellow');
                  setAnnotationNote('');
                  window.getSelection()?.removeAllRanges();
                }}
              >
                Отмена
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Панель аннотаций */}
      {showAnnotationsPanel && (
        <div className="annotations-panel fixed inset-y-0 right-0 w-80 bg-white dark:bg-dark-base-800 shadow-2xl z-40 border-l border-gray-200 dark:border-dark-base-700 flex flex-col">
          <div className="p-4 border-b border-gray-200 dark:border-dark-base-700 flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">📌 Аннотации</h3>
            <button
              onClick={() => setShowAnnotationsPanel(false)}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ✕
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {annotations.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                Нет аннотаций. Выделите текст в транскрипции чтобы создать.
              </p>
            ) : (
              annotations.map((annotation) => {
                // Находим часть транскрипции для получения текста
                const part = (transcript.parts as any[])?.find(p => p.id === annotation.part_id);
                // Текст без спикера (как в транскрипции)
                const fullText = part?.text || '';
                const textWithoutSpeaker = fullText.includes(':') 
                  ? fullText.split(':').slice(1).join(':').trim() 
                  : fullText;
                const highlightedText = textWithoutSpeaker.slice(annotation.start_char, annotation.end_char) || '';
                const colorConfig = ANNOTATION_COLORS.find(c => c.name === annotation.color);
                
                return (
                  <div
                    key={annotation.id}
                    data-annotation-id={annotation.id}
                    className={`group relative p-3 rounded-lg border transition-all ${colorConfig?.bg || 'bg-yellow-200 dark:bg-yellow-900/40'} border-gray-200 dark:border-dark-base-700 hover:shadow-md`}
                  >
                    {/* Кнопка удаления */}
                    <button
                      onClick={(e) => handleDeleteAnnotation(annotation.id, e)}
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-red-500/80 hover:bg-red-600 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Удалить аннотацию"
                    >
                      ✕
                    </button>
                    
                    <button
                      onClick={() => scrollToAnnotation(annotation)}
                      className="w-full text-left pr-6"
                    >
                      <p className="text-sm text-gray-800 dark:text-gray-200 line-clamp-2 mb-1">
                        "{highlightedText}"
                      </p>
                      {annotation.note && (() => {
                        const speakerName = fullText.split(':')[0] || '';
                        const speakerColor = speakerName ? getSpeakerColor(speakerName) : null;
                        return (
                          <p className={`text-xs italic mb-1 line-clamp-2 ${speakerColor?.text || 'text-gray-600 dark:text-gray-300'}`}>
                            💬 {annotation.note}
                          </p>
                        );
                      })()}
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {fullText.split(':')[0] || ''} • {colorConfig?.label || 'Жёлтый'}
                      </p>
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Toast уведомления */}
      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 px-4 py-3 rounded-lg shadow-lg z-50 transition-all ${
          toast.type === 'success' 
            ? 'bg-green-500 text-white' 
            : 'bg-red-500 text-white'
        }`}>
          <p className="text-sm font-medium">{toast.message}</p>
        </div>
      )}
    </div>
  );
};