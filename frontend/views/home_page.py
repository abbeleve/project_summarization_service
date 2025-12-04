import streamlit as st
import time
from components.sidebar import show_user_sidebar, show_admin_sidebar
from utils.api_client import APIClient
from utils.navigation import navigate
from config.settings import (
    SUPPORTED_FORMATS, 
    TRANSCRIBE_MODELS,
    TRANSCRIBE_LIBS,
    DIARIZATION_MODELS,
    DIARIZE_LIBS,
    LLM_MODELS
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

        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.success(f"📄 Файл: {uploaded_file.name}")
            
        with col2:
            st.info(f"📊 Размер: {uploaded_file.size:,} байт")
        

        with st.expander("⚙️ Настройки моделей", expanded=True):

            col_model1, col_model2 = st.columns(2)
            
            with col_model1:
                # Выбор модели транскрибации
                transcribe_model = st.selectbox(
                    "Модель транскрибации",
                    TRANSCRIBE_MODELS,
                    index=0,  # v3_ctc по умолчанию
                    help="Выберите модель для преобразования речи в текст"
                )
                
                # Выбор библиотеки транскрибации
                transcribe_lib = st.selectbox(
                    "Библиотека транскрибации",
                    TRANSCRIBE_LIBS,
                    index=0,  # gigaam по умолчанию
                    help="Выберите библиотеку для транскрибации"
                )
                
                # Выбор модели для суммаризации
                llm_model = st.selectbox(
                    "Модель суммаризации",
                    LLM_MODELS,
                    index=0,  # openai/gpt-oss-20b по умолчанию
                    help="Выберите модель для суммаризации текста"
                )
            
            with col_model2:
                # Выбор модели диаризации
                diarization_model = st.selectbox(
                    "Модель диаризации",
                    DIARIZATION_MODELS,
                    index=0,  # pyannote/speaker-diarization-community-1 по умолчанию
                    help="Выберите модель для определения спикеров"
                )
                
                # Выбор библиотеки диаризации
                diarize_lib = st.selectbox(
                    "Библиотека диаризации",
                    DIARIZE_LIBS,
                    index=0,  # pyannote по умолчанию
                    help="Выберите библиотеку для диаризации"
                )
        
        if st.button("🎯 Анализировать", type="primary", use_container_width=True):
            with st.spinner("🔍 Начинаем анализ..."):
                st.session_state.pending_analysis = {
                    "file": uploaded_file,
                    "filename": uploaded_file.name,
                    "transcribe_model": transcribe_model,
                    "diarization_model": diarization_model,
                    "diarize_lib": diarize_lib,
                    "transcribe_lib": transcribe_lib,
                    "llm_model": llm_model
                }
                st.rerun()

def show_history_section():
    st.subheader("📋 История транскрипций")

    # Проверяем доступность API
    if not APIClient.check_health():
        st.error("🚨 Сервер анализа недоступен")
        return

    transcripts = APIClient.get_transcripts()

    if not transcripts:
        st.info("📝 У вас пока нет транскрипций")
        return

    for transcript in transcripts:
        show_transcript_card(transcript)

def show_transcript_card(transcript: dict):
    """Отобразить карточку транскрипции"""
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**Транскрипция #{transcript.get('transcript_id', 'N/A')}**")
            
            # Подсчитываем статистику
            parts = transcript.get("parts", [])
            speakers_count = count_unique_speakers_card(parts)
            duration = calculate_duration_card(parts)
            
            st.caption(f"🗣️ {speakers_count} спикеров | ⏱️ {duration}")
            
            # Показываем превью текста
            if parts:
                first_part = parts[0].get("text", "") if parts else ""
                preview = first_part[:100] + "..." if len(first_part) > 100 else first_part
                st.write(preview)
        
        with col2:
            st.write("")
            if st.button("📊 Подробнее", key=f"view_{transcript.get('transcript_id')}", 
                        use_container_width=True):
                navigate("analysis", id=transcript.get("transcript_id"))

        st.markdown("---")

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

    with st.spinner("🔍 Анализируем аудиозапись..."):
        result = APIClient.process_audio(uploaded_file)

        if result:
            # Сохраняем результат в session_state
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