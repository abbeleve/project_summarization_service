from df.enhance import enhance, init_df, load_audio, save_audio

def denoise_file(input_path: str, output_path: str):
    model, df_state, _ = init_df()
    audio, _ = load_audio(input_path, sr=df_state.sr())
    enhanced = enhance(model, df_state, audio)
    save_audio(output_path, enhanced, df_state.sr())