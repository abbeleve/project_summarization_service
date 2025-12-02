import streamlit as st
import json
from datetime import datetime

def display_analysis_result(result: dict, filename: str):
    """Отобразить результаты анализа"""
    
    st.subheader("📊 Суммаризация встречи")
    if result.get("summary"):
        st.write(result["summary"])
    else:
        st.info("Суммаризация не доступна")
    
    st.subheader("📝 Детальная транскрипция")
    segments = result.get("transcription", [])
    
    for segment in segments:
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 3])
            with col1:
                st.metric(
                    label="Спикер", 
                    value=segment["speaker"]
                )
            with col2:
                st.write(f"**Время:** {segment['start']:.1f}s - {segment['end']:.1f}s")
            with col3:
                st.write(segment["text"])
    
    # Статистика
    st.subheader("📈 Статистика")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Количество спикеров", result.get("speakers_count", 0))
    with col2:
        st.metric("Длительность", result.get("duration", "—"))
    with col3:
        st.metric("Обработано", result.get("processed_by", "—"))

def display_transcription_segments(segments: list, clean_text: str, file_key: str):
    """Отобразить сегменты транскрипции"""
    
    if segments:
        for i, segment in enumerate(segments):
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    speaker = segment.get("speaker", "UNKNOWN")
                    start_time = segment.get("start", 0)
                    st.write(f"**{speaker}**")
                    st.caption(f"{start_time:.1f}s")
                with col2:
                    st.text_area(
                        "Текст",
                        value=segment.get("text", ""),
                        height=60,
                        label_visibility="collapsed",
                        key=f"segment_{file_key}_{i}"
                    )
                st.divider()
    else:
        # Если нет сегментов, показываем чистый текст
        st.info("ℹ️ Сегментированная транскрипция недоступна")
        if clean_text:
            st.text_area(
                "Чистый текст транскрипции",
                value=clean_text,
                height=200,
                label_visibility="collapsed",
                key=f"clean_text_{file_key}"
            )

def display_full_transcription(original_text: str, clean_text: str, file_key: str):
    """Отобразить полный текст транскрипции"""
    
    tab1, tab2 = st.tabs(["Оригинальный текст", "Очищенный текст"])
    
    with tab1:
        st.text_area(
            "Оригинальный текст (как распознано)",
            value=original_text,
            height=300,
            label_visibility="collapsed",
            key=f"original_{file_key}"
        )
    
    with tab2:
        st.text_area(
            "Очищенный текст (обработанный)",
            value=clean_text,
            height=300,
            label_visibility="collapsed",
            key=f"clean_{file_key}"
        )

def display_download_option(result: dict, filename: str, transcript_id: str):
    """Отобразить опцию скачивания"""
    
    col1, col2, col3 = st.columns(3)
    
    # JSON формат (полные данные)
    with col1:
        json_str = json.dumps(result, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 Скачать JSON",
            data=json_str,
            file_name=f"transcript_{transcript_id}_full.json",
            mime="application/json",
            use_container_width=True,
            key=f"download_json_{transcript_id}"
        )
    
    # Текстовый формат (только транскрипция)
    with col2:
        text_content = result.get("clean_text", result.get("original_text", ""))
        st.download_button(
            label="📄 Скачать текст",
            data=text_content,
            file_name=f"transcript_{transcript_id}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"download_txt_{transcript_id}"
        )
    
    # Суммаризация отдельно
    with col3:
        summary = result.get("summary", "")
        if summary:
            st.download_button(
                label="📋 Скачать суммаризацию",
                data=summary,
                file_name=f"summary_{transcript_id}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"download_summary_{transcript_id}"
            )
        else:
            st.button(
                "📋 Суммаризация недоступна",
                disabled=True,
                use_container_width=True
            )