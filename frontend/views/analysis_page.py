import streamlit as st
from components.sidebar import show_user_sidebar, show_admin_sidebar
from components.analysis_results import display_analysis_result, display_download_option, display_meeting_chat
from utils.api_client import APIClient
from utils.navigation import navigate

def show_analysis_page(transcript_id: str):
    if st.session_state.user_role == "admin":
        show_admin_sidebar()
    else:
        show_user_sidebar()
    
    if not transcript_id:
        st.error("❌ ID транскрипции не указан")
        if st.button("← Назад", use_container_width=True):
            navigate("home")
        return

    # Проверяем, есть ли у нас новая транскрипция в session_state
    current_analysis = st.session_state.get("current_analysis") or {}
    
    if current_analysis.get("is_new") and current_analysis.get("id") == transcript_id:
        show_new_analysis(current_analysis)
    else:
        show_historical_analysis(transcript_id)

def show_new_analysis(data: dict):
    """Показать только что созданную транскрипцию"""
    result = data["data"]
    filename = data["filename"]
    
    # Преобразуем структуру данных для отображения
    display_data = {
        "title": result.get("title", f"Транскрипция #{result.get('transcript_id', '')}"),
        "summary": result.get("summary", ""),
        "key_points": result.get("key_points", []),
        "transcription": convert_segments_to_display_format(result.get("segments", [])),
        "speakers_count": len(result.get("speakers", [])),
        "duration": f"{result.get('duration', 0):.1f} сек",
        "processed_by": st.session_state.get("username", "user"),
        "original_text": result.get("original_text", ""),
    }

    st.markdown("### ⬇️ Скачать результаты")
    display_download_option(
        result=display_data,
        filename=filename,
        transcript_id=data["id"]
    )
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(f"📊 {display_data['title']}")
        st.success("✅ Анализ завершён")
        st.caption(f"Файл: {filename}")

        # Показываем ключевые точки, если есть
        if display_data["key_points"]:
            with st.expander("🔑 Ключевые точки", expanded=True):
                for i, point in enumerate(display_data["key_points"], 1):
                    st.write(f"{i}. {point}")

    with col2:
        if st.button("← Назад", use_container_width=True):
            navigate("home")


    st.markdown("---")
    col_transcript, col_chat = st.columns([2, 1])  # 2/3 транскрипция, 1/3 чат

    with col_transcript:
        display_analysis_result(display_data, f"transcript_{filename}.txt")

    with col_chat:
        st.markdown("### 💬 Чат с LLM")
        display_meeting_chat(filename)


def show_historical_analysis(transcript_id: str):
    """Показать существующую транскрипцию из БД"""
    data = APIClient.get_transcript_by_id(transcript_id)

    if not data:
        st.error("Транскрипция не найдена")
        if st.button("← Назад", use_container_width=True):
            navigate("home")
        return
    
    # Преобразуем структуру данных для отображения
    display_data = {
        "title": data.get("title", f"Транскрипция #{transcript_id}"),
        "summary": data.get("summary", ""),
        "key_points": data.get("key_points", []),
        "transcription": convert_parts_to_display_format(data.get("parts", [])),
        "speakers_count": count_unique_speakers(data.get("parts", [])),
        "duration": calculate_duration(data.get("parts", [])),
        "processed_by": "Система",
        "original_text": data.get("original_text", ""),
    }

    st.markdown("### ⬇️ Скачать результаты")
    display_download_option(
        result=display_data,
        filename=f"transcript_{transcript_id}.txt",
        transcript_id=transcript_id
    )
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(f"📊 {display_data['title']}")
        st.caption(f"🗣️ {display_data['speakers_count']} спикеров | ⏱️ {display_data['duration']}")
        
        # Показываем ключевые точки, если есть
        if display_data["key_points"]:
            with st.expander("🔑 Ключевые точки", expanded=True):
                for i, point in enumerate(display_data["key_points"], 1):
                    st.write(f"{i}. {point}")
                    
    with col2:
        if st.button("← Назад", use_container_width=True):
            navigate("home")

    st.markdown("---")
    col_transcript, col_chat = st.columns([2, 1])  # 2/3 транскрипция, 1/3 чат

    with col_transcript:
        display_analysis_result(display_data, f"transcript_{transcript_id}.txt")

    with col_chat:
        st.markdown("### 💬 Чат с LLM")
        display_meeting_chat(transcript_id)

def convert_segments_to_display_format(segments: list) -> list:
    """Конвертировать сегменты из API в формат для отображения"""
    return [
        {
            "speaker": segment.get("Speaker", "UNKNOWN"),
            "start": segment.get("start", 0),
            "end": segment.get("stop", 0),
            "text": segment.get("Text", "")
        }
        for segment in segments
    ]

def convert_parts_to_display_format(parts: list) -> list:
    """Конвертировать части транскрипции из БД в формат для отображения"""
    result = []
    for part in parts:
        text = part.get("text", "")
        # Извлекаем спикера из текста (формат "SPEAKER_01: текст")
        if ":" in text:
            speaker, text_content = text.split(":", 1)
            speaker = speaker.strip()
            text = text_content.strip()
        else:
            speaker = "UNKNOWN"
        
        result.append({
            "speaker": speaker,
            "start": part.get("start_time", 0) / 1000,  # Конвертируем мс в секунды
            "end": part.get("end_time", 0) / 1000,
            "text": text
        })
    return result

def count_unique_speakers(parts: list) -> int:
    """Посчитать уникальных спикеров"""
    speakers = set()
    for part in parts:
        text = part.get("text", "")
        if ":" in text:
            speaker = text.split(":", 1)[0].strip()
            speakers.add(speaker)
    return len(speakers)

def calculate_duration(parts: list) -> str:
    """Рассчитать общую длительность"""
    if not parts:
        return "0 сек"
    
    max_time = max(part.get("end_time", 0) for part in parts)
    duration_sec = max_time / 1000
    
    if duration_sec < 60:
        return f"{duration_sec:.1f} сек"
    else:
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        return f"{minutes} мин {seconds} сек"