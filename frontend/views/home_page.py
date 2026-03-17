import streamlit as st
import time
from datetime import datetime
from components.sidebar import show_user_sidebar, show_admin_sidebar
from utils.api_client import APIClient
from utils.navigation import navigate
from config.settings import (
    SUPPORTED_FORMATS,
    TRANSCRIBE_CONFIG,
    DIARIZATION_CONFIG,
    LLM_MODELS,
    get_transcribe_models_by_lib,
    get_diarization_models_by_lib
)

def show_home_page():
    if st.session_state.user_role == "admin":
        show_admin_sidebar()
    else:
        show_user_sidebar()

    # Сбрасываем пагинацию на страницу 0
    if "page" not in st.session_state:
        st.session_state.page = 0

    process_pending_analysis()

    st.header("🎙️ Анализатор встреч")
    show_upload_section()
    st.markdown("---")
    show_history_section()

# Максимальный размер файла для шумоподавления (200 MB)
MAX_DENOISE_SIZE = 200 * 1024 * 1024

def show_upload_section():
    st.subheader("📤 Новый анализ")

    uploaded_file = st.file_uploader(
        "Загрузите аудиофайл для анализа",
        type=SUPPORTED_FORMATS,
        help="Поддерживаемые форматы: " + ", ".join(SUPPORTED_FORMATS)
    )


    if uploaded_file:
        # === Определяем, новый ли файл ===
        previous_file = st.session_state.get("last_uploaded_filename")
        current_file = uploaded_file.name

        if previous_file != current_file:
            # Сбрасываем всё состояние, связанное с аудио
            keys_to_clear = [
                "original_audio",
                "denoised_audio",
                "denoise_ready",
                "denoise_attempted",
                "denoise_error"
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.last_uploaded_filename = current_file

        st.session_state.original_audio = uploaded_file

        # === Проверка размера файла перед шумоподавлением ===
        if uploaded_file.size > MAX_DENOISE_SIZE:
            st.error(f"⚠️ Файл слишком большой для шумоподавления (макс. {MAX_DENOISE_SIZE // 1024 // 1024} MB)")
            st.session_state.denoise_ready = False
            st.session_state.denoise_error = f"Файл превышает лимит {MAX_DENOISE_SIZE // 1024 // 1024} MB"
        # Обрабатываем шумоподавление, если ещё не делали для ЭТОГО файла
        elif "denoise_attempted" not in st.session_state:
            with st.spinner("🔊 Применяю шумоподавление..."):
                denoised_bytes = APIClient.apply_noise_suppression(uploaded_file)
                if denoised_bytes:
                    st.session_state.denoised_audio = denoised_bytes
                    st.session_state.denoise_ready = True
                else:
                    st.session_state.denoise_ready = False
                    st.session_state.denoise_error = "Не удалось применить шумоподавление"
            st.session_state.denoise_attempted = True

        col1, col2 = st.columns([1, 1])
        with col1:
            st.success(f"📄 Файл: {uploaded_file.name}")
        with col2:
            st.info(f"📊 Размер: {uploaded_file.size:,} байт")

        # === Отображение плееров ===
        st.markdown("### 🎧 Оригинал")
        st.audio(uploaded_file)

        if st.session_state.get("denoise_ready"):
            st.markdown("### 🎧 С шумоподавлением")
            from io import BytesIO
            st.audio(BytesIO(st.session_state.denoised_audio), format="audio/wav")

        # === Настройки моделей ===
        with st.expander("⚙️ Настройки моделей", expanded=True):
            col_model1, col_model2 = st.columns(2)
            with col_model1:
                st.markdown("**Транскрибация**")
                transcribe_lib = st.selectbox(
                    "Библиотека",
                    list(TRANSCRIBE_CONFIG.keys()),
                    index=0,
                    help="Выберите библиотеку для транскрибации",
                    key="transcribe_lib_select"
                )
                transcribe_models = get_transcribe_models_by_lib(transcribe_lib)
                transcribe_model = st.selectbox(
                    "Модель",
                    transcribe_models,
                    index=0 if transcribe_models else 0,
                    help="Выберите модель для преобразования речи в текст",
                    key="transcribe_model_select"
                )
                st.markdown("**Суммаризация**")
                llm_model = st.selectbox(
                    "Модель суммаризации",
                    LLM_MODELS,
                    index=0,
                    help="Выберите модель для суммаризации текста",
                    key="llm_select"
                )
                noise_sup_bool = st.checkbox(
                    "🔇 Использовать шумоподавление",
                    value=False,
                    help="Применить подавление шумов для улучшения качества транскрибации"
                )

            with col_model2:
                st.markdown("**Диаризация**")
                diarize_lib = st.selectbox(
                    "Библиотека",
                    list(DIARIZATION_CONFIG.keys()),
                    index=0,
                    help="Выберите библиотеку для диаризации",
                    key="diarize_lib_select"
                )
                diarization_models = get_diarization_models_by_lib(diarize_lib)
                diarization_model = st.selectbox(
                    "Модель",
                    diarization_models,
                    index=0 if diarization_models else 0,
                    help="Выберите модель для определения спикеров",
                    key="diarization_model_select"
                )

        # === Кнопка анализа ===
        denoise_ready = st.session_state.get("denoise_ready", False)
        denoise_requested = noise_sup_bool

        # Блокируем кнопку, если шумоподавление запрошено, но не готово
        disable_analyze = denoise_requested and not denoise_ready

        if disable_analyze:
            st.warning("⏳ Ожидание завершения обработки шумоподавления...")
            analyze_clicked = False
        else:
            analyze_clicked = st.button(
                "🎯 Анализировать", 
                type="primary", 
                use_container_width=True,
                disabled=disable_analyze
            )

        if analyze_clicked:
            if denoise_requested and denoise_ready:
                class FakeUploadFile:
                    def __init__(self, name, content, mime_type="audio/wav"):
                        self.name = name
                        self._content = content
                        self.type = mime_type
                    def getvalue(self):
                        return self._content

                audio_to_send = FakeUploadFile(
                    name=f"denoised_{uploaded_file.name}",
                    content=st.session_state.denoised_audio,
                    mime_type="audio/wav"
                )
            else:
                audio_to_send = uploaded_file

            # Отправляем задачу и получаем task_id
            with st.spinner("🚀 Отправка задачи на обработку..."):
                result = APIClient.process_audio(
                    audio_to_send,
                    transcribe_model=transcribe_model,
                    diarization_model=diarization_model,
                    diarize_lib=diarize_lib,
                    transcribe_lib=transcribe_lib,
                    llm_model=llm_model,
                    noise_sup_bool=str(noise_sup_bool).lower()
                )
                
                if result and result.get("task_id"):
                    # Сохраняем task_id для polling
                    st.session_state.pending_task_id = result.get("task_id")
                    st.session_state.pending_filename = uploaded_file.name
                    st.info(f"✅ Задача отправлена! Task ID: `{result.get('task_id')[:8]}...`")
                    st.session_state.pending_analysis = None  # Очищаем pending_analysis
                    st.rerun()
                else:
                    st.error("❌ Ошибка при отправке задачи")
        
        

def show_history_section():
    st.subheader("📋 История транскрипций")

    if not APIClient.check_health():
        st.error("🚨 Сервер анализа недоступен")
        return

    # Инициализация пагинации в session_state
    if "page" not in st.session_state:
        st.session_state.page = 0
    
    ITEMS_PER_PAGE = 10

    # Получаем транскрипции с пагинацией
    result = APIClient.get_transcripts(limit=ITEMS_PER_PAGE, offset=st.session_state.page * ITEMS_PER_PAGE)
    
    transcripts = result.get("items", [])
    total = result.get("total", 0)
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if not transcripts:
        st.info("📝 У вас пока нет транскрипций")
        return

    # Отображаем транскрипции
    for transcript in transcripts:
        show_transcript_card(transcript)

    # Пагинация
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("◀ Назад", disabled=st.session_state.page == 0, use_container_width=True):
            st.session_state.page -= 1
            st.rerun()
    
    with col2:
        st.write(f"**Страница {st.session_state.page + 1} из {max(1, total_pages)}**")
        st.write(f"Всего записей: {total}")
    
    with col3:
        if st.button("Вперед ▶", disabled=st.session_state.page >= total_pages - 1, use_container_width=True):
            st.session_state.page += 1
            st.rerun()

def parse_created_at(created_at_str: str) -> datetime:
    """Парсит строку с датой в datetime"""
    try:
        if created_at_str:
            # Пробуем разные форматы
            try:
                return datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except:
                # Если не ISO формат, пробуем другие
                for fmt in ["%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.strptime(created_at_str, fmt)
                    except:
                        continue
    except:
        pass
    return datetime.min  # Если не удалось распарсить, возвращаем минимальную дату

def show_transcript_card(transcript: dict):
    """Отобразить карточку транскрипции"""
    transcript_id = transcript.get('transcript_id', 'N/A')
    title = transcript.get('title', f'Транскрипция #{transcript_id}')
    meeting_type = transcript.get('meeting_type', 'Не определено')
    
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Заголовок с ID
            st.write(f"**{title}**")
            # Тип совещания
            st.markdown(
                f"""
                <div style="
                    display: inline-block;
                    background-color: #e0e0e0;
                    color: #333333;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 0.85em;
                    font-weight: 500;
                    margin-top: 4px;
                    border: none;
                    box-shadow: none;
                ">{meeting_type}</div><br>  <!-- ← Перенос строки -->
                """,
                unsafe_allow_html=True
            )
            
            # Отображаем дату создания, если есть
            created_at = transcript.get("created_at")
            if created_at:
                try:
                    dt = parse_created_at(created_at)
                    date_str = dt.strftime("%d.%m.%Y %H:%M")
                    st.caption(f"📅 Создано: {date_str}")
                except:
                    pass
            
            # Подсчитываем статистику
            parts = transcript.get("parts", [])
            speakers_count = count_unique_speakers_card(parts)
            duration = calculate_duration_card(parts)
            
            st.caption(f"🗣️ {speakers_count} спикеров | ⏱️ {duration}")

            summary = transcript.get("summary")
            key_points = transcript.get("key_points", [])
            
            if key_points and len(key_points) > 0:
                # Показываем первые 2 ключевые точки
                preview_points = key_points[:2]
                for i, point in enumerate(preview_points, 1):
                    st.write(f"• {point[:80]}{'...' if len(point) > 80 else ''}")
                if len(key_points) > 2:
                    st.caption(f"... и ещё {len(key_points) - 2} пунктов")
            elif summary:
                preview = summary[:150] + "..." if len(summary) > 150 else summary
                st.write(preview)
            elif parts:
                first_part = parts[0].get("text", "") if parts else ""
                preview = first_part[:100] + "..." if len(first_part) > 100 else first_part
                st.write(preview)
        
        with col2:
            # Вертикальное расположение кнопок
            button_col1, button_col2 = st.columns([1, 1])
            
            with button_col1:
                if st.button("📊", 
                           key=f"view_{transcript_id}",
                           help="Подробнее",
                           use_container_width=True):
                    navigate("analysis", id=transcript_id)
            
            with button_col2:
                if st.button("🗑️",
                           key=f"delete_{transcript_id}",
                           help="Удалить",
                           type="secondary",
                           use_container_width=True):
                    # Показываем подтверждение удаления
                    st.session_state.pending_delete = transcript_id
                    st.rerun()
        
        # Проверяем, нужно ли показывать диалог удаления
        if st.session_state.get("pending_delete") == transcript_id:
            show_delete_confirmation(transcript_id)
        
        st.markdown("---")

def show_delete_confirmation(transcript_id: str):
    """Показать диалог подтверждения удаления"""
    with st.container():
        st.warning("⚠️ Вы уверены, что хотите удалить эту транскрипцию?")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Да, удалить", 
                        key=f"confirm_delete_{transcript_id}",
                        type="primary",
                        use_container_width=True):
                success = APIClient.delete_transcript(transcript_id)
                if success:
                    st.success("✅ Транскрипция удалена")
                    if "pending_delete" in st.session_state:
                        del st.session_state.pending_delete
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Не удалось удалить транскрипцию")
        
        with col2:
            if st.button("❌ Отмена",
                        key=f"cancel_delete_{transcript_id}",
                        use_container_width=True):
                # Отменяем удаление
                if "pending_delete" in st.session_state:
                    del st.session_state.pending_delete
                st.rerun()

def count_unique_speakers_card(parts: list) -> int:
    speakers = set()
    for part in parts:
        text = part.get("text", "")
        if ":" in text:
            speaker = text.split(":", 1)[0].strip()
            speakers.add(speaker)
    return len(speakers)

def calculate_duration_card(parts: list) -> str:
    if not parts:
        return "0 сек"
    
    max_time = max((part.get("end_time", 0) for part in parts), default=0)
    duration_sec = max_time / 1000
    
    if duration_sec < 60:
        return f"{duration_sec:.1f} сек"
    else:
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        return f"{minutes} мин {seconds} сек"

def process_pending_analysis():
    """Polling для отслеживания статуса задачи"""
    # Проверяем есть ли задача в процессе
    task_id = st.session_state.get("pending_task_id")
    if not task_id:
        return

    # Показываем прогресс
    st.markdown("### 🔄 Прогресс обработки")
    
    # Получаем статус задачи
    task_status = APIClient.get_task_status(task_id)
    
    if not task_status:
        st.error("❌ Не удалось получить статус задачи")
        st.session_state.pending_task_id = None
        return
    
    status = task_status.get("status", "unknown")
    step = task_status.get("step", "unknown")
    progress = task_status.get("progress", {})
    error = task_status.get("error")
    result = task_status.get("result")
    
    # Отображаем прогресс бар
    percent = progress.get("percent", 0) if isinstance(progress, dict) else 0
    step_name = progress.get("step", step) if isinstance(progress, dict) else step
    
    # Маппинг шагов на понятные названия
    step_names = {
        "transcription": "🎤 Транскрибация",
        "summarization": "📝 Суммаризация",
        "db_save": "💾 Сохранение в БД",
        "rag_index": "🔍 RAG индексирование",
        "completed": "✅ Готово",
        "failed": "❌ Ошибка"
    }
    
    display_step = step_names.get(step_name, step_name)
    
    # Прогресс бар
    st.progress(percent / 100)
    st.info(f"**{display_step}**... {percent}%")
    
    # Логи статуса
    if status == "pending":
        st.warning("⏳ Задача ожидает обработки...")
        time.sleep(2)
        st.rerun()
        
    elif status == "processing":
        st.success(f"⚙️ Обработка: {display_step}")
        time.sleep(3)  # Polling каждые 3 секунды
        st.rerun()
        
    elif status == "completed":
        st.success("✅ Обработка завершена успешно!")
        
        # Получаем transcript_id из результата
        transcript_id = None
        if result and isinstance(result, dict):
            transcript_id = result.get("transcript_id")
        
        if transcript_id:
            st.session_state.pending_task_id = None
            st.session_state.page = 0  # Сбрасываем пагинацию
            time.sleep(1)
            navigate("analysis", id=transcript_id)
        else:
            st.error("❌ Задача завершена, но не удалось получить transcript_id")
            st.session_state.pending_task_id = None
            
    elif status == "failed":
        st.error(f"❌ Ошибка обработки: {error or 'Неизвестная ошибка'}")
        st.session_state.pending_task_id = None
        
    else:
        st.warning(f"⚠️ Неизвестный статус: {status}")
        st.session_state.pending_task_id = None