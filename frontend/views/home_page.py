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

    process_pending_analysis()

    st.header("🎙️ Анализатор встреч")
    show_upload_section()
    st.markdown("---")
    show_history_section()

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
                "denoise_attempted"
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.last_uploaded_filename = current_file

        st.session_state.original_audio = uploaded_file

        # Обрабатываем шумоподавление, если ещё не делали для ЭТОГО файла
        if "denoise_attempted" not in st.session_state:
            st.session_state.denoise_attempted = True
            with st.spinner("🔊 Применяю шумоподавление..."):
                denoised_bytes = APIClient.apply_noise_suppression(uploaded_file)
                if denoised_bytes:
                    st.session_state.denoised_audio = denoised_bytes
                    st.session_state.denoise_ready = True
                else:
                    st.session_state.denoise_ready = False

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

            with st.spinner("🔍 Начинаем анализ..."):
                st.session_state.pending_analysis = {
                    "file": audio_to_send,
                    "filename": uploaded_file.name,
                    "transcribe_model": transcribe_model,
                    "diarization_model": diarization_model,
                    "diarize_lib": diarize_lib,
                    "transcribe_lib": transcribe_lib,
                    "llm_model": llm_model,
                    "noise_sup_bool": str(noise_sup_bool).lower()
                }
                st.rerun()
        
        

def show_history_section():
    st.subheader("📋 История транскрипций")

    if not APIClient.check_health():
        st.error("🚨 Сервер анализа недоступен")
        return

    transcripts = APIClient.get_transcripts()

    if not transcripts:
        st.info("📝 У вас пока нет транскрипций")
        return

    # Сортируем транскрипции по дате создания (сверху новые)
    transcripts_sorted = sorted(
        transcripts,
        key=lambda x: parse_created_at(x.get("created_at", "")),
        reverse=True  # Сверху новые
    )

    for transcript in transcripts_sorted:
        show_transcript_card(transcript)

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
    if not st.session_state.get("pending_analysis"):
        return
    
    pending = st.session_state.pending_analysis
    uploaded_file = pending["file"]
    
    st.info(f"""
    ⚙️ **Настройки анализа:**
    - Модель транскрибации: `{pending.get('transcribe_model', 'v3_ctc')}`
    - Библиотека транскрибации: `{pending.get('transcribe_lib', 'gigaam')}`
    - Модель диаризации: `{pending.get('diarization_model', 'pyannote/speaker-diarization-community-1')}`
    - Библиотека диаризации: `{pending.get('diarize_lib', 'pyannote')}`
    - Модель суммаризации: `{pending.get('llm_model', 'openai/gpt-oss-20b')}`
    """)

    with st.spinner("🔍 Анализируем аудиозапись..."):
        result = APIClient.process_audio(
            uploaded_file,
            transcribe_model=pending.get('transcribe_model'),
            diarization_model=pending.get('diarization_model'),
            diarize_lib=pending.get('diarize_lib'),
            transcribe_lib=pending.get('transcribe_lib'),
            llm_model=pending.get('llm_model'),
            noise_sup_bool=str(pending.get('noise_sup_bool', 'false'))
        )

        if result:
            st.session_state.current_analysis = {
                "id": result.get("transcript_id", "new"),
                "data": result,
                "filename": pending["filename"],
                "is_new": True
            }
            st.session_state.pending_analysis = None
            navigate("analysis", id=result.get("transcript_id", "new"))
        else:
            st.error("❌ Ошибка при анализе аудиофайла")
            st.session_state.pending_analysis = None