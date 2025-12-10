import streamlit as st
import json
from datetime import datetime
import plotly.express as px
from utils.api_client import APIClient

def display_analysis_result(result: dict, filename: str):
    """Отобразить результаты анализа"""
    
    st.subheader("📊 Суммаризация встречи")
    if result.get("summary"):
        st.write(result["summary"])
    else:
        st.info("Суммаризация не доступна")
    
    st.markdown("---")
    display_speaker_time_distribution(result.get("transcription", []))

    st.markdown("---")
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
    st.markdown("---")
    st.subheader("📈 Статистика")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Количество спикеров", result.get("speakers_count", 0))
    with col2:
        st.metric("Длительность", result.get("duration", "—"))
    with col3:
        st.metric("Обработано", result.get("processed_by", "—"))

def display_speaker_time_distribution(segments: list):
    """Отобразить круговую диаграмму и таблицу долей в одной строке"""
    
    if not segments:
        st.info("Нет данных о сегментах для построения диаграммы.")
        return
    
    # Собираем время по спикерам
    speaker_times = {}
    for segment in segments:
        speaker = segment.get("speaker", "UNKNOWN")
        start = segment.get("start", 0.0)
        end = segment.get("end", 0.0)
        duration = max(0.0, end - start)
        
        if speaker not in speaker_times:
            speaker_times[speaker] = 0.0
        speaker_times[speaker] += duration
    
    total_duration = sum(speaker_times.values())
    if total_duration == 0:
        st.info("Общая длительность разговора равна 0 секунд.")
        return
    
    # Подготовка данных
    data = {
        "Спикер": list(speaker_times.keys()),
        "Время (сек)": list(speaker_times.values())
    }
    percentages = [f"{(t / total_duration * 100):.1f}%" for t in data["Время (сек)"]]
    data["Доля (%)"] = percentages

    # Выводим заголовок НАД колонками
    st.markdown("### 🗣️ Распределение времени по спикерам")

    # Создаем 2 колонки
    col1, col2 = st.columns([2, 1])

    with col1:
        # Круговая диаграмма БЕЗ заголовка, с явным указанием легенды
        fig = px.pie(
            data,
            names="Спикер",
            values="Время (сек)",
            title=" ",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(
            template="plotly_dark",
            font=dict(size=14),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                title=" "
            ),
            margin=dict(t=10, b=20, l=20, r=20),
            title_x=0.5
        )
        fig.update_traces(
            textinfo='percent+label',
            textfont_size=12,
            pull=[0.05] * len(data["Спикер"])
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Таблица
        st.markdown("#### 📊 Доли")
        st.dataframe(
            {
                "Спикер": data["Спикер"],
                "Время (сек)": [f"{t:.1f}" for t in data["Время (сек)"]],
                "Доля (%)": data["Доля (%)"]
            },
            use_container_width=True,
            hide_index=True,
            height=300
        )

def display_meeting_chat(transcript_id: str):
    chat_key = f"chat_{transcript_id}"
    print(transcript_id)
    # 🔥 Загружаем историю из API, если ещё не загружена
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
        # Загружаем из бэкенда
        history = APIClient.get_chat_history(transcript_id)
        if history:
            st.session_state[chat_key] = history

    chat_container = st.container(height=1000, border=True)

    with chat_container:
        for msg in st.session_state[chat_key]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Спросите о встрече...", key=f"chat_input_{transcript_id}"):
        # Добавляем новый вопрос
        st.session_state[chat_key].append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Анализирую..."):
                    response_data = APIClient.ask_question(transcript_id, prompt)
                    answer = response_data.get("answer", "Ошибка.")
                
                st.markdown(answer)
                st.session_state[chat_key].append({"role": "assistant", "content": answer})
                
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
    
    col1, col2 = st.columns(2)
    
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
    
    # Суммаризация отдельно
    with col2:
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