import torch
from df.enhance import enhance, init_df, load_audio, save_audio

# Настройки батчинга
BATCH_DURATION_SEC = 60  # Длительность одного батча (сек)
OVERLAP_SEC = 0.5  # Перекрытие между батчами для плавных переходов


def denoise_file(input_path: str, output_path: str):
    """
    Шумоподавление с батчингом для больших файлов.
    
    Args:
        input_path: Путь к входному аудиофайлу
        output_path: Путь для сохранения очищенного аудио
    """
    model, df_state, _ = init_df()
    sample_rate = df_state.sr()
    
    # Загружаем всё аудио
    audio, _ = load_audio(input_path, sr=sample_rate)
    
    # Определяем размер батча в сэмплах
    batch_samples = int(BATCH_DURATION_SEC * sample_rate)
    overlap_samples = int(OVERLAP_SEC * sample_rate)
    
    total_samples = audio.shape[-1]
    
    # Если аудио короткое, обрабатываем целиком
    if total_samples <= batch_samples:
        enhanced = enhance(model, df_state, audio)
        save_audio(output_path, enhanced, sample_rate)
        return
    
    # Обрабатываем батчами
    enhanced_chunks = []
    start_sample = 0
    
    while start_sample < total_samples:
        # Определяем конец батча
        end_sample = min(start_sample + batch_samples, total_samples)
        
        # Добавляем overlap для плавности (кроме последнего батча)
        if end_sample < total_samples:
            overlap_end = end_sample + overlap_samples
            chunk = audio[:, start_sample:overlap_end]
        else:
            chunk = audio[:, start_sample:end_sample]
        
        # Обрабатываем батч
        enhanced_chunk = enhance(model, df_state, chunk)
        
        # Убираем overlap если это не последний батч
        if end_sample < total_samples:
            enhanced_chunk = enhanced_chunk[:, :-overlap_samples]
        
        enhanced_chunks.append(enhanced_chunk)
        start_sample = end_sample
    
    # Склеиваем батчи
    enhanced = torch.cat(enhanced_chunks, dim=-1)
    save_audio(output_path, enhanced, sample_rate)