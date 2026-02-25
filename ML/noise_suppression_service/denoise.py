from df.enhance import enhance, init_df, load_audio, save_audio
import torch

torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('medium')

def denoise_file(input_path: str, output_path: str):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    model, df_state, _ = init_df()
    model = model.to(device)
    
    audio, _ = load_audio(input_path, sr=df_state.sr())
    enhanced = enhance(model, df_state, audio)
    save_audio(output_path, enhanced, df_state.sr())
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()