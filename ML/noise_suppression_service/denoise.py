import torch
import librosa
import logging
from df.enhance import enhance, init_df, save_audio

# Настройки батчинга
BATCH_DURATION_SEC = 60  # Длительность одного батча (сек)
OVERLAP_SEC = 0.5  # Перекрытие между батчами для плавных переходов

logger = logging.getLogger(__name__)


def denoise_file(input_path: str, output_path: str):
    """
    Шумоподавление с батчингом для больших файлов.

    Загружает и обрабатывает аудио чанками по BATCH_DURATION_SEC,
    без загрузки всего файла в RAM.

    Args:
        input_path: Путь к входному аудиофайлу
        output_path: Путь для сохранения очищенного аудио
    """
    model, df_state, _ = init_df()
    model_sr = df_state.sr()

    total_duration = librosa.get_duration(path=input_path)
    overlap_samples = int(OVERLAP_SEC * model_sr)

    enhanced_chunks = []
    start_time = 0.0

    while start_time < total_duration:
        chunk_duration = min(BATCH_DURATION_SEC, total_duration - start_time)
        is_last = (start_time + chunk_duration >= total_duration)

        # Для не-последних чанков читаем с запасом на overlap
        read_duration = chunk_duration + (0 if is_last else OVERLAP_SEC)

        # Загружаем только этот чанк (librosa делает ресемплинг если нужно)
        chunk_np, _ = librosa.load(
            input_path, sr=model_sr, mono=True,
            offset=start_time, duration=read_duration,
        )

        # Добавляем размерность канала: (samples,) → (1, samples)
        chunk = torch.from_numpy(chunk_np).unsqueeze(0).float()

        # Обрабатываем чанк
        enhanced_chunk = enhance(model, df_state, chunk)

        # Убираем overlap для не-последних чанков
        if not is_last:
            enhanced_chunk = enhanced_chunk[:, :-overlap_samples]

        enhanced_chunks.append(enhanced_chunk)
        start_time += chunk_duration

        logger.debug(
            f"Чанк: {start_time:.0f}s / {total_duration:.0f}s "
            f"({start_time / total_duration * 100:.0f}%)"
        )

    # Склеиваем чанки
    enhanced = torch.cat(enhanced_chunks, dim=-1)
    save_audio(output_path, enhanced, model_sr)
    logger.info(f"Шумоподавление завершено: {output_path}")