from df.enhance import enhance, init_df, load_audio, save_audio
import torch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Оптимизации для производительности на GPU
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('medium')

def denoise_file(input_path: str, output_path: str):
    # Используем CUDA
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")

    try:
        # Инициализация модели
        logger.info("Loading DeepFilterNet model...")
        model, df_state, _ = init_df()
        model = model.to(device)
        model.eval()
        logger.info("Model loaded successfully")

        # Загрузка аудио
        logger.info(f"Loading audio from: {input_path}")
        audio, _ = load_audio(input_path, sr=df_state.sr())
        logger.info(f"Audio loaded: shape={audio.shape}, sample_rate={df_state.sr()}")

        # Применение шумоподавления
        logger.info("Applying noise suppression...")
        enhanced = enhance(model, df_state, audio)
        logger.info(f"Noise suppression applied: shape={enhanced.shape}")

        # Сохранение результата
        logger.info(f"Saving cleaned audio to: {output_path}")
        save_audio(output_path, enhanced, df_state.sr())
        logger.info("Audio saved successfully")

        # Очистка памяти GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU memory cleared")

    except Exception as e:
        logger.error(f"Noise suppression failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise RuntimeError(f"Noise suppression failed: {str(e)}") from e
