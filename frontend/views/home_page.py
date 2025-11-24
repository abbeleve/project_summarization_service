import streamlit as st
import time
from components.sidebar import show_user_sidebar, show_admin_sidebar
from utils.api_client import APIClient
from utils.navigation import navigate
from config.settings import SUPPORTED_FORMATS

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
        type=SUPPORTED_FORMATS
    )

    if uploaded_file:
        col1, col2 = st.columns([2, 2])
        with col1:
            st.success(f"Файл: {uploaded_file.name}")
            context_for_transcription = st.text_input("Контекст для транскрибации")
        with col2:
            st.info(f"Размер файла: {uploaded_file.size:,} байт")
            context_for_summarization = st.text_input("Контекст для суммаризации")

        if st.button("🎯 Анализировать", type="primary"):
            st.session_state.pending_analysis = {
                "file": uploaded_file,
                "filename": uploaded_file.name
            }
            st.rerun()

def show_history_section():
    st.subheader("📋 История анализов")

    search_query = st.text_input(
        "🔍 Поиск по совещаниям",
        placeholder="Введите название или ключевые слова..."
    )

    analysis_history = APIClient.get_analysis_history(search_query)

    if not analysis_history:
        st.info("📝 История пуста")
        return

    for meeting in analysis_history:
        show_meeting_card(meeting)

def show_meeting_card(meeting: dict):
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**{meeting['title']}**")
            st.caption(f"📅 {meeting['date']} | ⏱️ {meeting['duration']} | 👥 {meeting['speakers_count']}")
            st.write(meeting['summary_preview'])
        
        with col2:
            st.write("")
            st.write("")
            if st.button("📊 Подробнее", key=f"view_{meeting['id']}", use_container_width=True):
                navigate("analysis", id=meeting["id"])

        st.markdown("---")

def process_pending_analysis():
    if not st.session_state.get("pending_analysis"):
        return
    
    pending = st.session_state.pending_analysis
    uploaded_file = pending["file"]

    with st.spinner("🔍 Анализируем запись..."):
        time.sleep(2)
        result = APIClient.process_audio(uploaded_file)

        if result:
            analysis_id = APIClient.save_analysis_result(pending["filename"], result)
            st.session_state.current_analysis = {
                "id": analysis_id,
                "data": result,
                "filename": pending["filename"],
                "is_new": True
            }

            st.session_state.pending_analysis = None
            navigate("analysis", id=analysis_id)
        else:
            st.error("Ошибка анализа")
            st.session_state.pending_analysis = None
