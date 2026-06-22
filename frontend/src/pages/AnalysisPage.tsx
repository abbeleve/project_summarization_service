import { useParams, useNavigate } from 'react-router-dom';
import { useRef, useState, useCallback, useEffect } from 'react';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useAnnotations } from '@/hooks/useAnnotations';
import { useCRMTasks, useCRMProjects, useCRMProjectBoards, useCRMProjectBoardColumns, useCRMProjectMembers } from '@/hooks/useCRM';
import { transcriptsApi } from '@/api/transcripts';
import type { MeetingTask } from '@/types/transcript';
import type { WeeekProject, WeeekBoard, WeeekBoardColumn, SendTaskBody } from '@/api/crm';
import { voiceApi, usersApi } from '@/api/voice';
import { getDominantColorsMap } from '@/utils/dominantColor';
import { SpeakerDistributionChart } from '@/components/analysis/SpeakerDistributionChart';
import { TranscriptSegment } from '@/components/analysis/TranscriptSegment';
import { AnnotatedText } from '@/components/analysis/AnnotatedText';
import { MeetingChat } from '@/components/analysis/MeetingChat';
import { AudioPlayer, type AudioPlayerHandle } from '@/components/audio/AudioPlayer';
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
  const audioPlayerRef = useRef<AudioPlayerHandle>(null);
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
  const [tasksExpanded, setTasksExpanded] = useState(true);
  const [keyPointsExpanded, setKeyPointsExpanded] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [audioError, setAudioError] = useState(false);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ===== Выбор project → board → column для отправки =====
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedBoardId, setSelectedBoardId] = useState<number | null>(null);
  const [selectedColumnId, setSelectedColumnId] = useState<number | null>(null);
  const [showProjectPicker, setShowProjectPicker] = useState(false);
  const [showBoardPicker, setShowBoardPicker] = useState(false);
  const [showColumnPicker, setShowColumnPicker] = useState(false);

  const { data: projects = [], isLoading: projectsLoading } = useCRMProjects();
  const { data: boards = [], isLoading: boardsLoading } = useCRMProjectBoards(selectedProjectId);
  const { data: columns = [], isLoading: columnsLoading } = useCRMProjectBoardColumns(selectedBoardId);

  // Участники выбранного проекта из Weeek для назначения задач
  const { data: memberList = [] } = useCRMProjectMembers(selectedProjectId);

  // ===== CRM (MeetingTasks) =====
  const {
    tasks: meetingTasks,
    isLoading: crmTasksLoading,
    isSendAllPending,
    sendAllToCRM,
    sendOneToCRM,
    isSendingOne,
    updateTask,
    deleteTask,
    isDeleting,
  } = useCRMTasks(transcript?.summary_id ?? null);

  const [openAssigneeFor, setOpenAssigneeFor] = useState<string | null>(null);
  const [openDeadlineFor, setOpenDeadlineFor] = useState<string | null>(null);
  const [draftDeadline, setDraftDeadline] = useState('');
  const [editingDescriptionId, setEditingDescriptionId] = useState<string | null>(null);
  const [editingDescriptionText, setEditingDescriptionText] = useState('');

  // Локальный выбор assignee и deadline — НЕ сохраняется в БД, сбрасывается при смене транскрипции
  const [localAssignees, setLocalAssignees] = useState<Record<string, string>>({});
  const [localDeadlines, setLocalDeadlines] = useState<Record<string, string>>({});
  // Сброс локального выбора при переходе на другой `/analysis/:id`
  useEffect(() => {
    setLocalAssignees({});
    setLocalDeadlines({});
    setTaskWeeekUserIds({});
    setOpenAssigneeFor(null);
    setOpenDeadlineFor(null);
  }, [id]);

  /** Сбросить выбор board/column при смене проекта. */
  const handleProjectSelect = (project: WeeekProject | null) => {
    setSelectedProjectId(project?.id ?? null);
    setSelectedBoardId(null);
    setSelectedColumnId(null);
    setShowProjectPicker(false);
  };
  const handleBoardSelect = (board: WeeekBoard | null) => {
    setSelectedBoardId(board?.id ?? null);
    setSelectedColumnId(null);
    setShowBoardPicker(false);
  };
  const handleColumnSelect = (col: WeeekBoardColumn | null) => {
    setSelectedColumnId(col?.id ?? null);
    setShowColumnPicker(false);
  };

  const selectedProject = projects.find((p) => p.id === selectedProjectId) ?? null;
  const selectedBoard = boards.find((b) => b.id === selectedBoardId) ?? null;
  const selectedColumn = columns.find((c) => c.id === selectedColumnId) ?? null;

  /** Собрать SendTaskBody из текущего выбора. */
  const getSendBody = (taskId?: string): SendTaskBody | undefined => {
    if (!selectedProjectId) return undefined;
    const body: SendTaskBody = { project_id: selectedProjectId, board_column_id: selectedColumnId };
    if (taskId && taskWeeekUserIds[taskId]) {
      body.user_id = taskWeeekUserIds[taskId];
    }
    if (taskId && localDeadlines[taskId]) {
      body.deadline = localDeadlines[taskId];
    }
    return body;
  };

  // Отслеживаем Weeek user_id для каждого task (заполняется при выборе assignee)
  const [taskWeeekUserIds, setTaskWeeekUserIds] = useState<Record<string, string>>({});

  const unsentTasks = meetingTasks.filter((t) => !t.sent_to_crm);
  const sentTasks = meetingTasks.filter((t) => t.sent_to_crm);
  const hasTasks = meetingTasks.length > 0;

  const handleSendAllToCRM = async () => {
    if (!transcript?.summary_id) return;
    if (unsentTasks.length === 0) {
      showToast('Все задачи уже отправлены', 'error');
      return;
    }
    if (!selectedProjectId) {
      showToast('Сначала выберите проект в Weeek', 'error');
      return;
    }
    sendAllToCRM(getSendBody(), {
      onSuccess: (res) => {
        if (res.status === 'ok' || res.status === 'partial') {
          showToast(`Отправлено ${res.sent} из ${res.total} задач в CRM`, 'success');
        } else {
          showToast(res.status === 'error' ? 'Ошибка отправки' : JSON.stringify(res), 'error');
        }
      },
      onError: (err) => {
        const msg = err instanceof Error ? err.message : 'Ошибка отправки в CRM';
        showToast(msg, 'error');
      },
    });
  };

  const handleSendOne = (taskId: string) => {
    if (!selectedProjectId) {
      showToast('Сначала выберите проект в Weeek', 'error');
      return;
    }
    sendOneToCRM({ taskId, body: getSendBody(taskId) }, {
      onSuccess: (res) => {
        if (res.status === 'ok') {
          showToast('Задача отправлена в CRM', 'success');
        } else if (res.status === 'already_sent') {
          showToast('Задача уже была отправлена', 'error');
        } else {
          showToast(res.message || 'Ошибка отправки', 'error');
        }
      },
      onError: (err) => {
        const msg = err instanceof Error ? err.message : 'Ошибка отправки';
        showToast(msg, 'error');
      },
    });
  };

  const ANNOTATION_COLORS = [
    { name: 'yellow', bg: 'bg-yellow-200 dark:bg-yellow-900/40', label: 'Жёлтый' },
    { name: 'green', bg: 'bg-green-200 dark:bg-green-900/40', label: 'Зелёный' },
    { name: 'blue', bg: 'bg-blue-200 dark:bg-blue-900/40', label: 'Синий' },
    { name: 'pink', bg: 'bg-pink-200 dark:bg-pink-900/40', label: 'Розовый' },
    { name: 'purple', bg: 'bg-blue-200 dark:bg-blue-900/40', label: 'Фиолетовый' },
  ];

  // Функция для прокрутки к нужному сегменту и перемотки аудио
  const handleSegmentClick = (segment: TranscriptSegmentType) => {
    // Перематываем аудио
    audioPlayerRef.current?.seekTo(segment.start);

    // Прокручиваем транскрипцию
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
      element.classList.add('ring-2', 'ring-blue-500', 'ring-offset-2');
      setTimeout(() => {
        element.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-2');
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
        panel.classList.add('ring-2', 'ring-blue-500');
        setTimeout(() => {
          panel.classList.remove('ring-2', 'ring-blue-500');
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

  // Конвертация Blob в URL для аудио (если есть)
  const audioUrl = transcript?.audio_url || (transcript?.audio_blob
    ? URL.createObjectURL(transcript.audio_blob)
    : '');

  // Сбрасываем audioError при смене транскрипции
  useEffect(() => {
    setAudioError(false);
  }, [audioUrl]);

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

  // Скачать JSON
  const handleDownloadJson = () => {
    const jsonStr = JSON.stringify(transcript, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${transcript.title || 'transcript'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ JSON скачан', 'success');
  };

  // Скачать отчёт (текстовый файл со всей информацией)
  const handleDownloadReport = () => {
    const lines: string[] = [];

    const separator = '='.repeat(60);
    const subSep = '-'.repeat(40);

    // --- Шапка ---
    lines.push(separator);
    lines.push(`  ОТЧЁТ: ${transcript.title}`);
    lines.push(separator);
    lines.push('');
    lines.push(`  Дата создания:    ${new Date(transcript.created_at).toLocaleString('ru-RU')}`);
    lines.push(`  Тип совещания:    ${transcript.meeting_type}`);
    lines.push(`  Длительность:     ${(() => {
      const secs = transcript.duration ? transcript.duration * 60 : (segments[segments.length - 1]?.stop || 0);
      const m = Math.floor(secs / 60);
      const s = Math.floor(secs % 60);
      return `${m} мин ${s} сек`;
    })()}`);
    lines.push(`  Кол-во спикеров:  ${new Set(segments.map(s => s.Speaker)).size}`);
    lines.push('');

    // --- Статистика спикеров ---
    const speakerTimes: Record<string, number> = {};
    segments.forEach(seg => {
      const speaker = seg.Speaker || 'UNKNOWN';
      speakerTimes[speaker] = (speakerTimes[speaker] || 0) + (seg.stop - seg.start);
    });
    const totalTime = Object.values(speakerTimes).reduce((a, b) => a + b, 0);
    const sortedSpeakers = Object.entries(speakerTimes).sort((a, b) => b[1] - a[1]);

    lines.push('--- Спикеры ---');
    lines.push(subSep);
    sortedSpeakers.forEach(([speaker, time]) => {
      const pct = totalTime > 0 ? ((time / totalTime) * 100).toFixed(1) : '0.0';
      const m = Math.floor(time / 60);
      const s = Math.floor(time % 60);
      lines.push(`  ${speaker.padEnd(20)} ${m} мин ${s.toString().padStart(2, '0')} сек  (${pct}%)`);
    });
    lines.push('');

    // --- Краткое содержание ---
    if (transcript.summary) {
      lines.push('--- Краткое содержание ---');
      lines.push(subSep);
      // Разбиваем summary на строки по 100 символов для читаемости
      const words = transcript.summary.split(' ');
      let line = '';
      words.forEach(word => {
        if ((line + ' ' + word).length > 100) {
          lines.push(`  ${line.trim()}`);
          line = word;
        } else {
          line += (line ? ' ' : '') + word;
        }
      });
      if (line) lines.push(`  ${line.trim()}`);
      lines.push('');
    }

    // --- Ключевые моменты ---
    if (transcript.key_points && transcript.key_points.length > 0) {
      lines.push('--- Ключевые моменты ---');
      lines.push(subSep);
      transcript.key_points.forEach((point, i) => {
        lines.push(`  ${i + 1}. ${point}`);
      });
      lines.push('');
    }

    // --- Аннотации ---
    if (annotations.length > 0) {
      lines.push('--- Аннотации ---');
      lines.push(subSep);
      annotations.forEach((ann, i) => {
        const part = transcript.parts?.find(p => p.id === ann.part_id);
        const speaker = part ? part.text.split(':')[0] || '' : '';
        const fullText = part?.text || '';
        const textWithoutSpeaker = fullText.includes(':')
          ? fullText.split(':').slice(1).join(':').trim()
          : fullText;
        const highlighted = textWithoutSpeaker.slice(ann.start_char, ann.end_char) || '';
        lines.push(`  [${i + 1}] ${speaker}: "${highlighted}"`);
        const colorNames: Record<string, string> = {
          yellow: 'Жёлтый', green: 'Зелёный', blue: 'Синий', pink: 'Розовый', purple: 'Фиолетовый',
        };
        lines.push(`       Цвет: ${colorNames[ann.color || 'yellow'] || ann.color}`);
        if (ann.note) lines.push(`       Заметка: ${ann.note}`);
        lines.push('');
      });
    }

    // --- Полная транскрипция ---
    lines.push('--- Полная транскрипция ---');
    lines.push(subSep);
    lines.push('');
    segments.forEach(seg => {
      const startM = Math.floor(seg.start / 60);
      const startS = Math.floor(seg.start % 60);
      const timestamp = `${startM.toString().padStart(2, '0')}:${startS.toString().padStart(2, '0')}`;
      lines.push(`  [${timestamp}] ${seg.Speaker}: ${seg.Text}`);
    });
    lines.push('');

    // --- Футер ---
    lines.push(separator);
    lines.push(`  Отчёт сгенерирован ${new Date().toLocaleString('ru-RU')}`);
    lines.push(separator);

    const text = lines.join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${transcript.title || 'transcript'}_report.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ Отчёт скачан', 'success');
  };

  return (
    <div className="-mx-6 px-6 space-y-6">
      {/* Шапка с кнопками навигации */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => navigate('/')}>
          ← Назад
        </Button>
      </div>

      {/* Заголовок транскрипции с мета-информацией */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          {isEditing ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename();
                if (e.key === 'Escape') setIsEditing(false);
              }}
              onBlur={() => setIsEditing(false)}
              className="text-3xl font-bold text-blue-600 dark:text-blue-400 bg-transparent border-b-2 border-blue-500 focus:outline-none px-1 py-0.5"
              autoFocus
            />
          ) : (
            <h1 className="text-3xl font-bold text-blue-600 dark:text-blue-400">
              {transcript.title}
            </h1>
          )}
          <button
            onClick={() => { setEditTitle(transcript.title); setIsEditing(v => !v); }}
            className="p-1.5 rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors cursor-pointer flex-shrink-0"
            title="Переименовать"
            type="button"
          >
            ✏️
          </button>
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400 flex-wrap">
          <span>🗣 {transcript.speakers?.length || new Set(segments.map(s => s.Speaker)).size} спикеров</span>
          <span>⏱ {(() => { const s = transcript.duration ? transcript.duration * 60 : (segments[segments.length - 1]?.stop || 0); return new Date(s * 1000).toISOString().slice(11, 19); })()}</span>
          <span>🔑 {transcript.key_points?.length || 0} ключ. моментов</span>
          <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark-base-800 text-gray-600 dark:text-gray-300 text-xs font-medium">
            {transcript.meeting_type}
          </span>
          <span className="flex items-center gap-1.5 ml-auto">
            <Button variant="secondary" size="sm" onClick={() => { navigator.clipboard.writeText(window.location.origin + '/analysis/' + id); showToast('🔗 Ссылка скопирована!', 'success'); }}>
              🔗 Поделиться
            </Button>
            <Button variant="secondary" size="sm" onClick={handleDownloadJson}>
              📥 Скачать JSON
            </Button>
            <Button variant="secondary" size="sm" onClick={handleDownloadReport}>
              📋 Скачать отчёт
            </Button>
          </span>
        </div>
      </div>

      {/* Аудиоплеер над транскрипцией и графиками */}
      {audioUrl && !audioError && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
          <AudioPlayer
            ref={audioPlayerRef}
            src={audioUrl}
            segments={segments}
            onError={() => setAudioError(true)}
          />
        </div>
      )}

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
              <h3 className="text-2xl font-bold text-blue-600 dark:text-blue-400">Детальная транскрипция</h3>
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
                <div className="h-full overflow-y-auto space-y-3 pr-2">
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

                  {/* Задачи (action items) — MeetingTask */}
                  {hasTasks && (
                    <div className="space-y-2">
                      <button
                        onClick={() => setTasksExpanded(!tasksExpanded)}
                        className="w-full flex items-center gap-2 text-left"
                      >
                        <span className="text-lg">✅</span>
                        <h4 className="text-2xl font-bold text-emerald-700 dark:text-emerald-300 flex-1">
                          Задачи
                        </h4>
                        {crmTasksLoading ? (
                          <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800/40 text-gray-400 text-xs">
                            загрузка…
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
                            {sentTasks.length > 0
                              ? `${unsentTasks.length} / ${meetingTasks.length}`
                              : meetingTasks.length}
                          </span>
                        )}
                        <span className="text-xs text-gray-400 px-1 select-none">
                          {tasksExpanded ? '▲' : '▼'}
                        </span>
                      </button>
                      <div
                        className={`transition-all ease-out ${tasksExpanded ? 'overflow-visible' : 'overflow-hidden'}`}
                        style={{
                          maxHeight: tasksExpanded ? '5000px' : '0px',
                          opacity: tasksExpanded ? 1 : 0,
                          transitionDuration: tasksExpanded ? '400ms' : '200ms',
                        }}
                      >
                        <div className="space-y-2 pt-2">

                          {/* Каскадный выбор: проект → доска → колонка */}
                          {unsentTasks.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2 px-1">
                              {/* Проект */}
                              <div className="relative">
                                <button
                                  onClick={() => { setShowProjectPicker(!showProjectPicker); setShowBoardPicker(false); setShowColumnPicker(false); }}
                                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                                    selectedProject
                                      ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                                      : 'bg-gray-100 dark:bg-gray-800/40 text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600'
                                  }`}
                                >
                                  📁 {selectedProject ? selectedProject.name : 'Проект'}
                                  <span className="text-[10px] opacity-60">{projectsLoading ? '…' : '▼'}</span>
                                </button>
                                {showProjectPicker && (
                                  <div className="absolute z-30 mt-1 left-0 w-64 rounded-lg bg-white dark:bg-dark-base-800 shadow-xl border border-gray-200 dark:border-dark-base-700 py-1 max-h-48 overflow-y-auto">
                                    <button
                                      onClick={() => handleProjectSelect(null)}
                                      className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-base-700"
                                    >
                                      — Не выбрано —
                                    </button>
                                    {projects.map((p) => (
                                      <button
                                        key={p.id}
                                        onClick={() => handleProjectSelect(p)}
                                        className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 dark:hover:bg-dark-base-700 ${
                                          selectedProjectId === p.id
                                            ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                                            : ''
                                        }`}
                                      >
                                        {p.name}
                                      </button>
                                    ))}
                                    {projects.length === 0 && !projectsLoading && (
                                      <p className="px-3 py-2 text-xs text-gray-400">Нет проектов</p>
                                    )}
                                  </div>
                                )}
                              </div>

                              {/* Доска */}
                              <div className="relative">
                                <button
                                  onClick={() => { if (selectedProjectId) { setShowBoardPicker(!showBoardPicker); setShowProjectPicker(false); setShowColumnPicker(false); } }}
                                  disabled={!selectedProjectId}
                                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                                    !selectedProjectId
                                      ? 'bg-gray-50 dark:bg-gray-800/20 text-gray-300 dark:text-gray-600 cursor-not-allowed'
                                      : selectedBoard
                                        ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                                        : 'bg-gray-100 dark:bg-gray-800/40 text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600'
                                  }`}
                                >
                                  📋 {selectedBoard ? selectedBoard.name : 'Доска'}
                                  {selectedProjectId && <span className="text-[10px] opacity-60">{boardsLoading ? '…' : '▼'}</span>}
                                </button>
                                {showBoardPicker && (
                                  <div className="absolute z-30 mt-1 left-0 w-64 rounded-lg bg-white dark:bg-dark-base-800 shadow-xl border border-gray-200 dark:border-dark-base-700 py-1 max-h-48 overflow-y-auto">
                                    <button
                                      onClick={() => handleBoardSelect(null)}
                                      className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-base-700"
                                    >
                                      — Не выбрано —
                                    </button>
                                    {boards.map((b) => (
                                      <button
                                        key={b.id}
                                        onClick={() => handleBoardSelect(b)}
                                        className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 dark:hover:bg-dark-base-700 ${
                                          selectedBoardId === b.id
                                            ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                                            : ''
                                        }`}
                                      >
                                        {b.name}
                                      </button>
                                    ))}
                                    {boards.length === 0 && !boardsLoading && (
                                      <p className="px-3 py-2 text-xs text-gray-400">Нет досок</p>
                                    )}
                                  </div>
                                )}
                              </div>

                              {/* Колонка */}
                              <div className="relative">
                                <button
                                  onClick={() => { if (selectedBoardId) { setShowColumnPicker(!showColumnPicker); setShowProjectPicker(false); setShowBoardPicker(false); } }}
                                  disabled={!selectedBoardId}
                                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                                    !selectedBoardId
                                      ? 'bg-gray-50 dark:bg-gray-800/20 text-gray-300 dark:text-gray-600 cursor-not-allowed'
                                      : selectedColumn
                                        ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                                        : 'bg-gray-100 dark:bg-gray-800/40 text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600'
                                  }`}
                                >
                                  📌 {selectedColumn ? selectedColumn.name : 'Колонка'}
                                  {selectedBoardId && <span className="text-[10px] opacity-60">{columnsLoading ? '…' : '▼'}</span>}
                                </button>
                                {showColumnPicker && (
                                  <div className="absolute z-30 mt-1 left-0 w-64 rounded-lg bg-white dark:bg-dark-base-800 shadow-xl border border-gray-200 dark:border-dark-base-700 py-1 max-h-48 overflow-y-auto">
                                    <button
                                      onClick={() => handleColumnSelect(null)}
                                      className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-base-700"
                                    >
                                      — Не выбрано —
                                    </button>
                                    {columns.map((c) => (
                                      <button
                                        key={c.id}
                                        onClick={() => handleColumnSelect(c)}
                                        className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 dark:hover:bg-dark-base-700 ${
                                          selectedColumnId === c.id
                                            ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                                            : ''
                                        }`}
                                      >
                                        {c.name}
                                      </button>
                                    ))}
                                    {columns.length === 0 && !columnsLoading && (
                                      <p className="px-3 py-2 text-xs text-gray-400">Нет колонок</p>
                                    )}
                                  </div>
                                )}
                              </div>

                              <span className="text-[10px] text-gray-400 ml-auto">
                                {selectedProject
                                  ? selectedColumn
                                    ? `→ ${selectedProject.name} / ${selectedBoard?.name} / ${selectedColumn.name}`
                                    : selectedBoard
                                      ? `→ ${selectedProject.name} / ${selectedBoard.name} / …`
                                      : `→ ${selectedProject.name} / …`
                                  : 'Выберите проект'}
                              </span>
                            </div>
                          )}

                          {unsentTasks.length > 0 && (
                            <div className="flex justify-end">
                              <button
                                onClick={(e) => { e.stopPropagation(); handleSendAllToCRM(); }}
                                disabled={isSendAllPending || !selectedProjectId}
                                className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-wait transition-colors shadow-sm cursor-pointer"
                              >
                                {isSendAllPending
                                  ? 'Отправка…'
                                  : `📤 Отправить всё (${unsentTasks.length})`}
                              </button>
                            </div>
                          )}

                          {meetingTasks.map((task: MeetingTask) => {
                            const isSent = task.sent_to_crm;
                            const containerClass = isSent
                              ? 'border-l-4 border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/20 rounded-lg p-4 shadow-sm opacity-60'
                              : 'border-l-4 border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-4 shadow-md';

                            return (
                              <div key={task.id} className={containerClass}>
                                <div className="flex items-start gap-3">
                                  <span
                                    className={`flex-shrink-0 w-6 h-6 rounded-full text-white text-xs font-bold flex items-center justify-center mt-0.5 ${
                                      isSent
                                        ? 'bg-gray-400'
                                        : 'bg-emerald-500'
                                    }`}
                                  >
                                    {meetingTasks.indexOf(task) + 1}
                                  </span>
                                  <div className="flex-1 min-w-0">
                                    {isSent ? (
                                      <p className="text-sm leading-relaxed text-gray-500 dark:text-gray-400 line-through">
                                        {task.description}
                                      </p>
                                    ) : editingDescriptionId === task.id ? (
                                      <div className="space-y-1">
                                        <textarea
                                          autoFocus
                                          value={editingDescriptionText}
                                          onChange={(e) => setEditingDescriptionText(e.target.value)}
                                          onKeyDown={(e) => {
                                            if (e.key === 'Escape') {
                                              setEditingDescriptionId(null);
                                              setEditingDescriptionText('');
                                            }
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                              e.preventDefault();
                                              if (editingDescriptionText.trim()) {
                                                updateTask({
                                                  taskId: task.id,
                                                  description: editingDescriptionText.trim(),
                                                });
                                              }
                                              setEditingDescriptionId(null);
                                              setEditingDescriptionText('');
                                            }
                                          }}
                                          onBlur={() => {
                                            if (editingDescriptionText.trim() && editingDescriptionText.trim() !== task.description) {
                                              updateTask({
                                                taskId: task.id,
                                                description: editingDescriptionText.trim(),
                                              });
                                            }
                                            setEditingDescriptionId(null);
                                            setEditingDescriptionText('');
                                          }}
                                          className="w-full border border-emerald-300 dark:border-emerald-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-dark-base-800 text-emerald-900 dark:text-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                                          rows={3}
                                        />
                                        <p className="text-[10px] text-gray-400">
                                          ↵ Enter — сохранить · Esc — отмена · Shift+↵ — новая строка
                                        </p>
                                      </div>
                                    ) : (
                                      <p
                                        className="text-sm leading-relaxed text-emerald-900 dark:text-emerald-100 cursor-pointer hover:bg-emerald-100/50 dark:hover:bg-emerald-800/30 rounded px-1 -mx-1 transition-colors"
                                        onClick={() => {
                                          setEditingDescriptionId(task.id);
                                          setEditingDescriptionText(task.description);
                                        }}
                                        title="Редактировать задачу"
                                      >
                                        {task.description}
                                      </p>
                                    )}

                                    {isSent ? (
                                      /* Отправленная — только информация */
                                      <div className="flex flex-wrap items-center gap-2 mt-2">
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-green-100 dark:bg-green-800/30 text-green-700 dark:text-green-300 text-[10px] font-medium">
                                          ✅ Отправлено в Weeek
                                        </span>
                                        {task.sent_at && (
                                          <span className="text-[10px] text-gray-400">
                                            {new Date(task.sent_at).toLocaleDateString(
                                              'ru-RU',
                                              { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }
                                            )}
                                          </span>
                                        )}
                                        {task.assignee && (
                                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800/40 text-gray-600 dark:text-gray-400 text-[10px]">
                                            👤 {task.assignee}
                                          </span>
                                        )}
                                        {task.deadline && (
                                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800/40 text-gray-600 dark:text-gray-400 text-[10px]">
                                            ⏰ {new Date(task.deadline).toLocaleDateString(
                                                'ru-RU',
                                                { day: '2-digit', month: '2-digit', year: 'numeric' }
                                              )}
                                          </span>
                                        )}
                                        <button
                                          onClick={() => {
                                            if (window.confirm('Удалить задачу?')) {
                                              deleteTask(task.id);
                                            }
                                          }}
                                          disabled={isDeleting}
                                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer disabled:opacity-50"
                                          title="Удалить задачу"
                                        >
                                          🗑️
                                        </button>
                                      </div>
                                    ) : (
                                      /* Неотправленная — редактирование */
                                      <div
                                        className="flex flex-wrap items-start gap-2 mt-2"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        {/* Assignee — выбор из участников Weeek (локально, не сохраняется в БД) */}
                                        <div className="relative">
                                          <button
                                            onClick={() =>
                                              setOpenAssigneeFor(
                                                openAssigneeFor === task.id ? null : task.id
                                              )
                                            }
                                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs cursor-pointer transition-colors ${
                                              (localAssignees[task.id] ?? task.assignee)
                                                ? 'bg-emerald-100 dark:bg-emerald-800/40 text-emerald-800 dark:text-emerald-200 hover:bg-emerald-200 dark:hover:bg-emerald-700/50'
                                                : 'bg-gray-100 dark:bg-gray-800/40 text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700/50'
                                            }`}
                                            title="Назначить ответственного"
                                          >
                                            👤 {(localAssignees[task.id] ?? task.assignee) || 'Назначить'}
                                          </button>
                                          {openAssigneeFor === task.id && (
                                            <div className="absolute z-20 mt-1 left-0 w-56 max-h-60 overflow-y-auto rounded-lg bg-white dark:bg-dark-base-800 shadow-xl border border-gray-200 dark:border-dark-base-700 py-1">
                                              {[
                                                { id: '', name: '— Не назначать —' },
                                                ...memberList,
                                              ].map((user) => (
                                                <button
                                                  key={user.id || 'none'}
                                                  onClick={() => {
                                                    const newAssignee = user.id ? user.name : '';
                                                    setLocalAssignees((prev) => ({ ...prev, [task.id]: newAssignee }));
                                                    if (user.id) {
                                                      setTaskWeeekUserIds((prev) => ({ ...prev, [task.id]: user.id }));
                                                    } else {
                                                      setTaskWeeekUserIds((prev) => {
                                                        const copy = { ...prev };
                                                        delete copy[task.id];
                                                        return copy;
                                                      });
                                                    }
                                                    setOpenAssigneeFor(null);
                                                  }}
                                                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 dark:hover:bg-dark-base-700 ${
                                                    (localAssignees[task.id] ?? task.assignee) ===
                                                      (user.id ? user.name : '') &&
                                                    'bg-emerald-50 dark:bg-emerald-900/30'
                                                  }`}
                                                >
                                                  {user.name}
                                                </button>
                                              ))}
                                            </div>
                                          )}
                                        </div>

                                        {/* Deadline — пресеты + свой date (локально, не сохраняется в БД) */}
                                        <div className="flex flex-wrap items-center gap-1">
                                          <button
                                            onClick={() => {
                                              const current = localDeadlines[task.id] ?? task.deadline;
                                              if (current) {
                                                setLocalDeadlines((prev) => {
                                                  const copy = { ...prev };
                                                  delete copy[task.id];
                                                  return copy;
                                                });
                                              } else {
                                                const today = new Date().toISOString().slice(0, 10);
                                                setLocalDeadlines((prev) => ({ ...prev, [task.id]: today }));
                                              }
                                              setOpenDeadlineFor(null);
                                            }}
                                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs cursor-pointer transition-colors ${
                                              (localDeadlines[task.id] ?? task.deadline)
                                                ? 'bg-amber-100 dark:bg-amber-800/40 text-amber-800 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-700/50'
                                                : 'bg-gray-100 dark:bg-gray-800/40 text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700/50'
                                            }`}
                                            title={(localDeadlines[task.id] ?? task.deadline) ? 'Убрать срок' : 'Установить срок'}
                                          >
                                            ⏰{' '}
                                            {(localDeadlines[task.id] ?? task.deadline)
                                              ? new Date(localDeadlines[task.id] ?? task.deadline).toLocaleDateString('ru-RU', {
                                                  day: '2-digit',
                                                  month: '2-digit',
                                                  year: 'numeric',
                                                })
                                              : 'Срок'}
                                          </button>

                                          {[
                                            { label: 'Сегодня', days: 0 },
                                            { label: 'Завтра', days: 1 },
                                            { label: 'Неделя', days: 7 },
                                            { label: 'Месяц', days: 30 },
                                          ].map((p) => {
                                            const d = new Date();
                                            d.setDate(d.getDate() + p.days);
                                            const iso = d.toISOString().slice(0, 10);
                                            const effectiveDeadline = localDeadlines[task.id] ?? task.deadline;
                                            const active = effectiveDeadline === iso;
                                            return (
                                              <button
                                                key={p.label}
                                                onClick={() => {
                                                  setLocalDeadlines((prev) => ({ ...prev, [task.id]: iso }));
                                                  setOpenDeadlineFor(null);
                                                }}
                                                className={`px-2 py-0.5 rounded-md text-[10px] font-medium transition-colors ${
                                                  active
                                                    ? 'bg-amber-500 text-white'
                                                    : 'bg-amber-50/60 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-800/40 border border-amber-200 dark:border-amber-700/30'
                                                }`}
                                              >
                                                {p.label}
                                              </button>
                                            );
                                          })}

                                          {openDeadlineFor === task.id ? (
                                            <input
                                              type="date"
                                              autoFocus
                                              value={draftDeadline}
                                              onChange={(e) => setDraftDeadline(e.target.value)}
                                              onBlur={() => {
                                                if (draftDeadline) {
                                                  setLocalDeadlines((prev) => ({ ...prev, [task.id]: draftDeadline }));
                                                }
                                                setOpenDeadlineFor(null);
                                              }}
                                              className="px-2 py-0.5 rounded-md text-xs border border-amber-300 dark:border-amber-700 bg-white dark:bg-dark-base-800 text-amber-900 dark:text-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-400 [color-scheme] dark:opacity-100"
                                            />
                                          ) : (
                                            <button
                                              onClick={() => {
                                                const effectiveDeadline = localDeadlines[task.id] ?? task.deadline;
                                                const current =
                                                  effectiveDeadline?.match(/^\d{4}-\d{2}-\d{2}/)
                                                    ? effectiveDeadline.slice(0, 10)
                                                    : new Date().toISOString().slice(0, 10);
                                                setDraftDeadline(current);
                                                setOpenDeadlineFor(task.id);
                                              }}
                                              className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-50/60 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-800/40 border border-amber-200 dark:border-amber-700/30 transition-colors"
                                              title="Выбрать произвольную дату"
                                            >
                                              📅 Своя
                                            </button>
                                          )}
                                        </div>

                                        {/* Кнопка отправить одну задачу */}
                                        <button
                                          onClick={() => handleSendOne(task.id)}
                                          disabled={isSendingOne}
                                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-500/80 text-white hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-wait transition-colors cursor-pointer"
                                          title="Отправить эту задачу"
                                        >
                                          {isSendingOne ? '…' : '📤 Отправить'}
                                        </button>
                                        {/* Кнопка удалить задачу */}
                                        <button
                                          onClick={() => {
                                            if (window.confirm('Удалить задачу?')) {
                                              deleteTask(task.id);
                                            }
                                          }}
                                          disabled={isDeleting}
                                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer disabled:opacity-50"
                                          title="Удалить задачу"
                                        >
                                          🗑️
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Ключевые моменты — каждый в отдельном блоке */}
                  {(transcript.key_points || []).length > 0 && (
                    <div className="space-y-2">
                      <button
                        onClick={() => setKeyPointsExpanded(!keyPointsExpanded)}
                        className="w-full flex items-center gap-2 text-left"
                      >
                        <span className="text-lg">🔑</span>
                        <h4 className="text-2xl font-bold text-amber-900 dark:text-amber-300 flex-1">
                          Ключевые моменты
                        </h4>
                        <span className="px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-medium">
                          {(transcript.key_points || []).length}
                        </span>
                        <span className="text-xs text-gray-400 px-1 select-none">
                          {keyPointsExpanded ? '▲' : '▼'}
                        </span>
                      </button>
                      <div
                        className="overflow-hidden transition-all ease-out"
                        style={{
                          maxHeight: keyPointsExpanded ? '5000px' : '0px',
                          opacity: keyPointsExpanded ? 1 : 0,
                          transitionDuration: keyPointsExpanded ? '400ms' : '200ms',
                        }}
                      >
                        <div className="space-y-2 pt-2">
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
                      </div>
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none text-sm"
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
