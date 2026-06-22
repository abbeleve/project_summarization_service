import { useParams, useNavigate } from 'react-router-dom';
import { useRef, useState, useCallback, useEffect } from 'react';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useAnnotations } from '@/hooks/useAnnotations';
import { useCRMTasks, useCRMProjects, useCRMProjectBoards, useCRMProjectBoardColumns, useCRMWorskpaceMembers, useCRMStatus } from '@/hooks/useCRM';
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
import { TaskCard } from '@/components/crm/TaskCard';
import { StepDot, StepSeparator } from '@/components/crm/StepDot';
import { CrmDropdown } from '@/components/crm/CrmDropdown';

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
  const [popupPosition, setPopupPosition] = useState<{ x: number; y: number } | null>(null);
  const [popupAbove, setPopupAbove] = useState(true);
  const [selectedColor, setSelectedColor] = useState('yellow');
  const [annotationNote, setAnnotationNote] = useState('');
  const [rightTab, setRightTab] = useState<'summary' | 'charts' | 'chat' | 'annotations'>('summary');
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const [tasksExpanded, setTasksExpanded] = useState(true);
  const [keyPointsExpanded, setKeyPointsExpanded] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [audioError, setAudioError] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

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

  // Статус подключения Weeek. `crmConnected === null` пока запрос в полёте.
  const { data: crmStatus } = useCRMStatus();
  const crmConnected = crmStatus?.connected === true;

  // Запросы к Weeek уходят только когда ключ подключён — иначе бэкенд отдаёт 400
  // и UX становится непонятным ("пусто, не работает, почему?").
  const { data: projects = [], isLoading: projectsLoading } = useCRMProjects(crmConnected);
  const { data: boards = [], isLoading: boardsLoading } = useCRMProjectBoards(selectedProjectId);
  const { data: columns = [], isLoading: columnsLoading } = useCRMProjectBoardColumns(selectedBoardId);

  // Участники workspace из Weeek для назначения задач
  const { data: memberList = [] } = useCRMWorskpaceMembers(crmConnected);

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

  // Локальный выбор assignee и deadline — НЕ сохраняется в БД, сбрасывается при смене транскрипции
  const [localAssignees, setLocalAssignees] = useState<Record<string, string>>({});
  const [localDeadlines, setLocalDeadlines] = useState<Record<string, string>>({});
  // Сброс локального выбора при переходе на другой `/analysis/:id`
  useEffect(() => {
    setLocalAssignees({});
    setLocalDeadlines({});
    setTaskWeeekUserIds({});
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
    if (!window.confirm(`Отправить все ${unsentTasks.length} неотправленных задач в Weeek?\n\nЭто действие нельзя отменить.`)) {
      return;
    }
    sendAllToCRM(getSendBody(), {
      onSuccess: (res) => {
        if (res.status === 'ok' || res.status === 'partial') {
          // Сохраняем assignee и deadline для всех отправленных задач
          unsentTasks.forEach((t) => {
            const assignee = localAssignees[t.id];
            const deadline = localDeadlines[t.id];
            if (assignee !== undefined || deadline) {
              updateTask({ taskId: t.id, assignee: assignee !== undefined ? assignee : undefined, deadline: deadline || undefined });
            }
          });
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
          // Сохраняем локальный assignee и deadline в БД
          const localAssignee = localAssignees[taskId];
          const localDeadline = localDeadlines[taskId];
          if (localAssignee !== undefined || localDeadline) {
            updateTask({
              taskId,
              assignee: localAssignee !== undefined ? localAssignee : undefined,
              deadline: localDeadline || undefined,
            });
          }
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

    // Получаем координаты выделения для позиционирования попапа
    const rect = range.getBoundingClientRect();
    const popupWidth = 380;
    const popupHeight = 340;
    const gap = 12;

    // По умолчанию — над выделением
    let x = rect.left + rect.width / 2 - popupWidth / 2;
    let y = rect.top - popupHeight - gap;
    let above = true;

    // Коррекция по X: не выезжаем за левый край
    if (x < 16) x = 16;
    // Коррекция по X: не выезжаем за правый край
    if (x + popupWidth > window.innerWidth - 16) {
      x = window.innerWidth - popupWidth - 16;
    }

    // Если над выделением не помещается — показываем снизу
    if (y < 8) {
      y = rect.bottom + gap;
      above = false;
    }

    setPopupPosition({ x, y });
    setPopupAbove(above);
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
      setPopupPosition(null);
      setPopupAbove(true);
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

  // Закрытие попапа по Escape
  useEffect(() => {
    if (!showAnnotationPopup) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowAnnotationPopup(false);
        setSelectedText(null);
        setSelectedColor('yellow');
        setAnnotationNote('');
        setPopupPosition(null);
        setPopupAbove(true);
        window.getSelection()?.removeAllRanges();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showAnnotationPopup]);

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

  // Фильтрация по поисковому запросу
  const filteredSegments = searchQuery.trim()
    ? segments.filter(seg =>
        seg.Text.toLowerCase().includes(searchQuery.toLowerCase()) ||
        seg.Speaker.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : segments;

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
            {/* Поле поиска */}
            <div className="relative mb-3 flex-shrink-0">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Поиск по транскрипции..."
                className="w-full px-3 py-2 pl-9 rounded-lg border border-gray-200/40 dark:border-dark-base-700/40 bg-white/60 dark:bg-dark-base-900/60 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-colors"
              />
              <svg
                className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                >
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <div className="space-y-0 overflow-y-auto pr-2 flex-1 min-h-0">
              {filteredSegments.length === 0 ? (
                <div className="text-center text-gray-400 dark:text-gray-500 py-8 text-sm">
                  {searchQuery ? 'Ничего не найдено' : 'Нет данных транскрипции'}
                </div>
              ) : (
                filteredSegments.map((seg, idx) => (
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
                ))
              )}
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
                            <div className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-xl bg-gray-50/80 dark:bg-white/[0.02] ring-1 ring-gray-200 dark:ring-white/[0.06]">

                              {/* Шаги каскада */}
                              <div className="flex items-center gap-1.5">

                                {/* Шаг 1: Проект */}
                                <StepDot
                                  active={!!selectedProject}
                                  done={!!selectedProject && !selectedBoard}
                                  open={showProjectPicker}
                                  onClick={() => { setShowProjectPicker(!showProjectPicker); setShowBoardPicker(false); setShowColumnPicker(false); }}
                                  icon="📁"
                                  label={selectedProject?.name || 'Проект'}
                                  loading={projectsLoading}
                                  dropdown={
                                    <CrmDropdown
                                      empty="Нет проектов"
                                      items={projects.map((p) => ({
                                        key: String(p.id),
                                        label: p.name,
                                        selected: selectedProjectId === p.id,
                                        onSelect: () => handleProjectSelect(p),
                                      }))}
                                      onClear={() => handleProjectSelect(null)}
                                    />
                                  }
                                />

                                <StepSeparator active={!!selectedProject} />

                                {/* Шаг 2: Доска */}
                                <StepDot
                                  active={!!selectedBoard}
                                  done={!!selectedBoard && !selectedColumn}
                                  disabled={!selectedProjectId}
                                  open={showBoardPicker}
                                  onClick={() => { if (selectedProjectId) { setShowBoardPicker(!showBoardPicker); setShowProjectPicker(false); setShowColumnPicker(false); } }}
                                  icon="📋"
                                  label={selectedBoard?.name || 'Доска'}
                                  loading={boardsLoading}
                                  dropdown={
                                    <CrmDropdown
                                      empty="Нет досок"
                                      items={boards.map((b) => ({
                                        key: String(b.id),
                                        label: b.name,
                                        selected: selectedBoardId === b.id,
                                        onSelect: () => handleBoardSelect(b),
                                      }))}
                                      onClear={() => handleBoardSelect(null)}
                                    />
                                  }
                                />

                                <StepSeparator active={!!selectedBoard} />

                                {/* Шаг 3: Колонка */}
                                <StepDot
                                  active={!!selectedColumn}
                                  done={false}
                                  disabled={!selectedBoardId}
                                  open={showColumnPicker}
                                  onClick={() => { if (selectedBoardId) { setShowColumnPicker(!showColumnPicker); setShowProjectPicker(false); setShowBoardPicker(false); } }}
                                  icon="📌"
                                  label={selectedColumn?.name || 'Колонка'}
                                  loading={columnsLoading}
                                  dropdown={
                                    <CrmDropdown
                                      empty="Нет колонок"
                                      items={columns.map((c) => ({
                                        key: String(c.id),
                                        label: c.name,
                                        selected: selectedColumnId === c.id,
                                        onSelect: () => handleColumnSelect(c),
                                      }))}
                                      onClear={() => handleColumnSelect(null)}
                                    />
                                  }
                                />
                              </div>

                              <span className="text-[10px] text-gray-400 dark:text-gray-500 ml-auto">
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
                                className={`px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors shadow-sm cursor-pointer ${
                                  isSendAllPending ? 'cursor-wait' : 'disabled:cursor-not-allowed'
                                }`}
                              >
                                {isSendAllPending
                                  ? 'Отправка…'
                                  : `📤 Отправить всё (${unsentTasks.length})`}
                              </button>
                            </div>
                          )}

                          {/* Сначала неотправленные (с номерами), потом выполненные (только ✓) */}
                          {[...unsentTasks, ...sentTasks].map((task: MeetingTask, idx: number) => (
                            <TaskCard
                              key={task.id}
                              task={task}
                              index={idx}
                              showNumber={!task.sent_to_crm}
                              members={memberList}
                              cb={{
                                localAssignees,
                                setLocalAssignees,
                                taskWeeekUserIds,
                                setTaskWeeekUserIds,
                                localDeadlines,
                                setLocalDeadlines,
                                isSendingOne,
                                isDeleting,
                                onSend: handleSendOne,
                                onDelete: (taskId) => {
                                  if (window.confirm('Удалить задачу?')) {
                                    deleteTask(taskId);
                                  }
                                },
                                onSaveDescription: (taskId, text) => {
                                  updateTask({
                                    taskId,
                                    description: text,
                                  });
                                },
                              }}
                            />
                          ))}
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
                              className="group/kp border-l-4 border-amber-500 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-4 shadow-md transition-all duration-200 ease-out hover:bg-amber-100 hover:shadow-lg hover:border-amber-600 dark:hover:bg-amber-900/30 dark:hover:border-amber-400 dark:hover:shadow-[0_6px_24px_-6px_rgba(245,158,11,0.25)] cursor-default"
                            >
                              <div className="flex items-start gap-3">
                                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center mt-0.5 transition-transform duration-200 group-hover/kp:scale-110">
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

      {/* Попап «Создать аннотацию» — стеклянная карточка над выделением */}
      {showAnnotationPopup && selectedText && popupPosition && (
        <>
          {/* Прозрачный backdrop для закрытия по клику вне */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => {
              setShowAnnotationPopup(false);
              setSelectedText(null);
              setSelectedColor('yellow');
              setAnnotationNote('');
              setPopupPosition(null);
              setPopupAbove(true);
              window.getSelection()?.removeAllRanges();
            }}
          />
          {/* Стеклянная карточка */}
          <div
            className="fixed z-50 popup-enter"
            style={{
              left: popupPosition.x,
              top: popupPosition.y,
              width: 380,
            }}
          >
            {/* Стрелка-треугольник (смотрит вниз, если попап сверху; вверх — если снизу) */}
            <div
              className={`absolute left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-white dark:bg-[#0e1622] border-l border-t border-gray-200 dark:border-white/10`}
              style={
                popupAbove
                  ? { bottom: -6 }
                  : { bottom: 'auto', top: -6, transform: 'translateX(-50%) rotate(225deg)' }
              }
            />

            <div className="bg-white dark:bg-[#0e1622] rounded-2xl p-5 shadow-lg shadow-gray-200/50 dark:shadow-2xl dark:shadow-black/40 border border-gray-200 dark:border-white/10">
              <h3 className="text-base font-bold text-gray-900 dark:text-white mb-3">Создать аннотацию</h3>

              {/* Выделенный текст */}
              <div className="mb-3 p-3 bg-gray-50 dark:bg-white/[0.04] rounded-xl border border-gray-200 dark:border-white/10">
                <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed line-clamp-3">
                  "{selectedText.text}"
                </p>
              </div>

              {/* Цвета */}
              <div className="mb-3">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Цвет подсветки:</p>
                <div className="flex gap-2">
                  {ANNOTATION_COLORS.map((color) => (
                    <button
                      key={color.name}
                      onClick={() => setSelectedColor(color.name)}
                      className={`w-7 h-7 rounded-full ${color.bg} border-2 transition-all duration-150 ${
                        selectedColor === color.name
                          ? 'border-gray-900 dark:border-white scale-110 shadow-md'
                          : 'border-transparent hover:scale-105'
                      }`}
                      title={color.label}
                    />
                  ))}
                </div>
              </div>

              {/* Комментарий */}
              <div className="mb-4">
                <textarea
                  value={annotationNote}
                  onChange={(e) => setAnnotationNote(e.target.value)}
                  placeholder="Заметка (необязательно)..."
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-white/10 rounded-xl bg-gray-50 dark:bg-white/[0.04] text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 focus:outline-none resize-none text-sm transition-all"
                />
              </div>

              {/* Кнопки */}
              <div className="flex gap-2">
                <button
                  onClick={handleCreateAnnotation}
                  className="flex-1 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-700 hover:to-indigo-600 text-white text-sm font-medium shadow-lg shadow-indigo-500/25 hover:shadow-indigo-600/30 transition-all duration-150 active:scale-[0.97]"
                >
                  ✓ Подчеркнуть
                </button>
                <button
                  onClick={() => {
                    setShowAnnotationPopup(false);
                    setSelectedText(null);
                    setSelectedColor('yellow');
                    setAnnotationNote('');
                    setPopupPosition(null);
                    setPopupAbove(true);
                    window.getSelection()?.removeAllRanges();
                  }}
                  className="px-4 py-2 rounded-xl bg-gray-50 dark:bg-white/[0.04] hover:bg-gray-100 dark:hover:bg-white/[0.08] text-gray-600 dark:text-gray-300 text-sm font-medium border border-gray-200 dark:border-white/10 transition-all duration-150"
                >
                  Отмена
                </button>
              </div>
            </div>
          </div>
        </>
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
