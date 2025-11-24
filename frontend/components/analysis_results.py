import streamlit as st
import json

def display_analysis_result(result: dict, filename: str):
    """Отобразить результаты анализа"""
    # Создаем уникальный ключ на основе имени файла
    file_key = filename.replace(".", "_")
    
    # Суммаризация
    st.subheader("📊 Суммаризация встречи")
    st.text_area(
        "Текст",
        value=result["summary"],
        height=80,
        label_visibility="collapsed",
        key=f"summary_{file_key}"
    )
    
    # Детальная транскрипция
    st.subheader("📝 Детальная транскрипция")
    display_transcription_segments(result["transcription"], file_key)
    
    # Статистика
    display_analysis_stats(result, file_key)
    
    # Скачивание
    display_download_option(result, filename)

def display_transcription_segments(segments: list, file_key: str):
    """Отобразить сегменты транскрипции"""
    for i, segment in enumerate(segments):
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 3])
            with col1:
                st.metric(
                    label="Спикер", 
                    value=segment["speaker"],
                    delta=f"{segment['start']}s"
                )
            with col2:
                st.write(f"**Время:** {segment['start']}s - {segment['end']}s")
            with col3:
                st.text_area(
                    "Текст",
                    value=segment["text"],
                    height=80,
                    label_visibility="collapsed",
                    key=f"segment_{file_key}_{i}"
                )

def display_analysis_stats(result: dict, file_key: str):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Количество спикеров", result.get("speakers_count", "—"))
    with col2:
        st.metric("Длительность встречи", result.get("duration", "—"))
    with col3:
        st.metric("Обработано", result.get("processed_by", "—"))

def display_download_option(result: dict, filename: str):
    """Отобразить опцию скачивания"""
    st.subheader("💾 Скачать результаты")
    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 Скачать JSON",
        data=json_str,
        file_name=f"meeting_analysis_{filename.split('.')[0]}.json",
        mime="application/json",
        use_container_width=True,
        key=f"download_{filename.replace('.', '_')}"
    )