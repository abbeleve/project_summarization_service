import { useParams, useNavigate } from 'react-router-dom';
import { useRef, useState, useCallback, useEffect } from 'react';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useAnnotations } from '@/hooks/useAnnotations';
import { transcriptsApi } from '@/api/transcripts';
import { voiceApi, usersApi } from '@/api/voice';
import { getDominantColorsMap } from '@/utils/dominantColor';
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
  const [rightTab, setRightTab] = useState<'summary' | 'charts' | 'chat' | 'annotations'>('summary');
  const [summaryExpanded, setSummaryExpanded] = useState(false);
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
    // Переключаем на вкладку аннотаций
    setRightTab('annotations');

    // Прокручиваем к нужной аннотации
    setTimeout(() => {
      const panel = document.querySelector(`[data-annotation-id="${annotation.id}"]`);
      if (panel) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
        panel.classList.add('ring-2', 'ring-violet-500');
        setTimeout(() => {
          panel.classList.remove('ring-2', 'ring-violet-500');
        }, 2000);
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
    <div className="-mx-6 px-6 space-y-6">
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

      {/* Основная раскладка: транскрипция слева, суммаризация + ключевые моменты справа */}
      <div className="flex flex-col lg:flex-row">
        {/* Левая часть — транскрипция */}
        <div className="flex-[6] min-w-0">
          {/* Полная транскрипция */}
          <div
            ref={transcriptContainerRef}
            onMouseUp={handleTextSelection}
            className="bg-gray-100/30 dark:bg-dark-base-950/30 rounded-xl border border-gray-200/20 dark:border-dark-base-700/20 p-4 flex flex-col"
            style={{ height: 'calc(100vh - 200px)' }}
          >
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <h3 className="text-3xl font-bold text-blue-600 dark:text-blue-400">{transcript.title}</h3>
            </div>
            <div className="space-y-0 overflow-y-auto pr-2 flex-1 min-h-0">
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

        {/* Вертикальный разделитель */}
        <div className="hidden lg:block w-px bg-gray-300 dark:bg-dark-base-600 self-stretch mx-6" />

        {/* Правая часть — вкладки: сводка / графики / чат */}
        <div className="flex-[4] min-w-0">
          <div className="bg-gray-100/30 dark:bg-dark-base-950/30 rounded-xl border border-gray-200/20 dark:border-dark-base-700/20 p-4 flex flex-col"
            style={{ height: 'calc(100vh - 200px)' }}>
            {/* Кнопки вкладок */}
            <div className="flex gap-1 mb-4 pb-3 border-b border-gray-200/30 dark:border-dark-base-700/30 flex-shrink-0">
              <button
                onClick={() => setRightTab('summary')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  rightTab === 'summary'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-dark-base-800/50'
                }`}
              >
                📋 Сводка
              </button>
              <button
                onClick={() => setRightTab('charts')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  rightTab === 'charts'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-dark-base-800/50'
                }`}
              >
                📊 Графики
              </button>
              <button
                onClick={() => setRightTab('chat')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  rightTab === 'chat'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-dark-base-800/50'
                }`}
              >
                💬 Чат
              </button>
              <button
                onClick={() => setRightTab('annotations')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors relative ${
                  rightTab === 'annotations'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-dark-base-800/50'
                }`}
              >
                📌 Аннотации
                {annotations.length > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">
                    {annotations.length}
                  </span>
                )}
              </button>
            </div>

            {/* Контент вкладок — заполняет оставшееся место */}
            <div className="flex-1 overflow-hidden min-h-0">
              {rightTab === 'summary' && (
                <div className="h-full overflow-y-auto space-y-6 pr-2">
                  {/* Суммаризация — сворачиваемая */}
                  <button
                    onClick={() => setSummaryExpanded(!summaryExpanded)}
                    className="w-full flex items-center gap-2 text-left"
                  >
                    <span className="text-lg">📋</span>
                    <h4 className="text-2xl font-bold text-blue-600 dark:text-blue-400 flex-1">
                      Краткое содержание
                    </h4>
                  </button>
                  {transcript.summary && (
                    <div
                      className={`border-l-4 rounded-lg shadow-sm transition-all ease-out ${
                        summaryExpanded
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-blue-500/40 bg-blue-50/50 dark:bg-blue-900/10 cursor-pointer'
                      }`}
                      style={{ transitionDuration: summaryExpanded ? '500ms' : '300ms' }}
                      onClick={() => { if (!summaryExpanded) setSummaryExpanded(true); }}
                    >
                      <div
                        className="overflow-hidden transition-all ease-out"
                        style={{
                          maxHeight: summaryExpanded ? '2000px' : '3.6rem',
                          transitionDuration: summaryExpanded ? '500ms' : '300ms'
                        }}
                      >
                        <p className={`leading-relaxed text-sm p-4 pb-1 transition-all ${
                          summaryExpanded
                            ? 'text-blue-900 dark:text-blue-100'
                            : 'text-blue-900/60 dark:text-blue-100/60'
                        }`}
                        style={{ transitionDuration: summaryExpanded ? '400ms' : '200ms' }}>
                          {transcript.summary}
                        </p>
                      </div>
                      <div className={`flex justify-center pb-1.5 transition-all duration-200 ${
                        summaryExpanded ? 'opacity-100' : 'opacity-60'
                      }`}>
                        <button
                          onClick={(e) => { e.stopPropagation(); setSummaryExpanded(!summaryExpanded); }}
                          className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors p-0.5 text-xs"
                          title={summaryExpanded ? 'Свернуть' : 'Развернуть'}
                        >
                          {summaryExpanded ? '▲' : '▼'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Ключевые моменты — каждый в отдельном блоке */}
                  {(transcript.key_points || []).length > 0 && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">🔑</span>
                        <h4 className="text-2xl font-bold text-amber-900 dark:text-amber-300">
                          Ключевые моменты
                        </h4>
                      </div>
                      {(transcript.key_points || []).map((point, idx) => (
                        <div
                          key={idx}
                          className="border-l-4 border-amber-500 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-4 shadow-md"
                        >
                          <div className="flex items-start gap-3">
                            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                              {idx + 1}
                            </span>
                            <p className="text-amber-900 dark:text-amber-100 text-sm leading-relaxed">
                              {point}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  </div>
                )}

              {rightTab === 'charts' && (
                <div className="h-full overflow-y-auto space-y-6 pr-2">
                  {segments.length > 0 && (
                    <SpeakerDistributionChart
                      segments={segments}
                      onSegmentClick={handleSegmentClick}
                    />
                  )}

                  {segments.length > 0 && audioUrl && (
                    <AudioPlayer
                      src={audioUrl}
                      segments={segments}
                    />
                  )}
                </div>
              )}

              {rightTab === 'chat' && (
                <MeetingChat
                  transcriptId={id}
                  transcriptText={transcript.original_text}
                />
              )}

              {rightTab === 'annotations' && (
                <div className="h-full flex flex-col">
                  <div className="flex items-center gap-2 mb-4 flex-shrink-0">
                    <span className="text-lg">📌</span>
                    <h4 className="text-2xl font-bold text-gray-900 dark:text-white">
                      Аннотации
                    </h4>
                    {annotations.length > 0 && (
                      <span className="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium">
                        {annotations.length}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                    {annotations.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                        Нет аннотаций. Выделите текст в транскрипции чтобы создать.
                      </p>
                    ) : (
                      annotations.map((annotation) => {
                        const part = (transcript.parts as any[])?.find(p => p.id === annotation.part_id);
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
                            className={`group relative p-3 rounded-lg border transition-all cursor-pointer ${colorConfig?.bg || 'bg-yellow-200 dark:bg-yellow-900/40'} border-gray-200 dark:border-dark-base-700 hover:shadow-md`}
                            onClick={() => scrollToAnnotation(annotation)}
                          >
                            <button
                              onClick={(e) => handleDeleteAnnotation(annotation.id, e)}
                              className="absolute top-1 right-1 w-6 h-6 rounded-full bg-red-500/80 hover:bg-red-600 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
                              title="Удалить аннотацию"
                            >
                              ✕
                            </button>
                            <p className="text-sm text-gray-800 dark:text-gray-200 line-clamp-2 mb-1 pr-6">
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
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
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