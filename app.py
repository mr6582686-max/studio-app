import os, subprocess, whisper, torch, re, shutil
import gradio as gr
import arabic_reshaper
from bidi.algorithm import get_display

device = "cuda" if torch.cuda.is_available() else "cpu"
whisper_model = whisper.load_model("large-v3-turbo", device=device)

LANGUAGE_DICT = {
    "English": "en",
    "Urdu (اردو)": "ur",
    "Hindi (हिंदी)": "hi",
    "Arabic (العربية)": "ar",
    "Turkish (Türkçe)": "tr",
    "Chinese (中文)": "zh"
}

RTL_CORRECTIONS = {
    r"\bامیر\b": "امید",
    r"\bگر\b": "گھر",
    r"\bکوشکایت\b": "کو شکایت",
    r"\bبارش\b": "وارث",
    r"\bماجی\b": "ماں جی",
}

def fix_rtl_script(text, lang_code):
    text = text.strip()
    if lang_code in ["ur", "ar"]:
        for wrong, right in RTL_CORRECTIONS.items():
            text = re.sub(wrong, right, text)
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    return text

def convert_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    ms = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{sec:02d}.{ms:02d}"

def process_master_studio(video_input, target_language, font_size, text_color, pitch_level, voice_effect, remove_music, enable_copyright_shield):
    try:
        if video_input is None:
            return None, "Error: Pehle video upload karein!"

        raw_input = "raw_input_video.mp4"
        shutil.copy(video_input, raw_input)

        raw_audio = "extracted_speech.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_input,
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            raw_audio
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        cleaned_audio = raw_audio
        if remove_music:
            demucs_out = "demucs_separated"
            os.makedirs(demucs_out, exist_ok=True)
            
            subprocess.run([
                "demucs", "--two-stems=vocals", "-n", "htdemucs",
                "--shifts=1", "-d", device,
                "-o", demucs_out, raw_audio
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            isolated_vocal = os.path.join(demucs_out, "htdemucs", "extracted_speech", "vocals.wav")
            if os.path.exists(isolated_vocal):
                cleaned_audio = isolated_vocal

        final_audio = "processed_final_audio.wav"
        pitch_rate = str(int(44100 * pitch_level))
        tempo_rate = str(round(1.0 / pitch_level, 3))
        
        audio_filters = [f"asetrate={pitch_rate}", f"atempo={tempo_rate}"]
        
        if voice_effect == "Deep Male":
            audio_filters.append("equalizer=f=120:width_type=h:width=200:g=6,bass=g=4")
        elif voice_effect == "High Female / Kid":
            audio_filters.append("equalizer=f=3200:width_type=h:width=1000:g=5,treble=g=4")
        elif voice_effect == "Radio / Telephone":
            audio_filters.append("highpass=f=300,lowpass=f=3000")
            
        af_chain = ",".join(audio_filters)
        
        subprocess.run([
            "ffmpeg", "-y", "-i", cleaned_audio,
            "-af", af_chain,
            final_audio
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        selected_lang = LANGUAGE_DICT.get(target_language, "en")
        task_type = "translate" if selected_lang == "en" else "transcribe"
        
        result = whisper_model.transcribe(
            cleaned_audio,
            task=task_type,
            language=None if task_type == "translate" else selected_lang,
            fp16=torch.cuda.is_available(),
            beam_size=1,
            best_of=1
        )

        color_map = {
            "Yellow": "&H0000FFFF",
            "White": "&H00FFFFFF",
            "Green": "&H0000FF00",
            "Cyan": "&H00FFFF00"
        }
        primary_color = color_map.get(text_color, "&H0000FFFF")

        ass_path = "output_subtitles.ass"
        ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: DefaultStyle,DejaVu Sans,{font_size},{primary_color},&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,2,1,2,10,10,18,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        with open(ass_path, "w", encoding="utf-8-sig") as f:
            f.write(ass_header)
            for segment in result['segments']:
                start_time, end_time, speech_text = segment['start'], segment['end'], segment['text'].strip()
                formatted_dialogue = fix_rtl_script(speech_text, selected_lang)
                if not formatted_dialogue:
                    continue

                f.write(f"Dialogue: 0,{convert_time(start_time)},{convert_time(end_time)},DefaultStyle,,0,0,0,,{formatted_dialogue}\n")

        video_filters = []
        if enable_copyright_shield:
            video_filters.append("hflip")

        ass_path_escaped = ass_path.replace(":", "\\:")
        video_filters.append(f"ass={ass_path_escaped}")
        vf_chain = ",".join(video_filters)

        final_video = "final_output_video.mp4"
        
        ffmpeg_render = [
            "ffmpeg", "-y",
            "-i", raw_input,
            "-i", final_audio,
            "-vf", vf_chain,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-c:a", "aac", "-b:a", "96k",
            "-threads", "0",
            final_video
        ]
        subprocess.run(ffmpeg_render, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return final_video, "⚡ Success! Studio processing complete!"

    except Exception as e:
        return None, f"Error: {str(e)}"

interface = gr.Interface(
    fn=process_master_studio,
    inputs=[
        gr.Video(label="📹 Upload Video"),
        gr.Dropdown(choices=list(LANGUAGE_DICT.keys()), value="English", label="🌐 Select Subtitle Language"),
        gr.Slider(minimum=12, maximum=32, step=1, value=18, label="🔤 Subtitle Font Size"),
        gr.Radio(choices=["Yellow", "White", "Green", "Cyan"], value="Yellow", label="🎨 Caption Color"),
        gr.Slider(minimum=0.70, maximum=1.30, step=0.02, value=0.88, label="🎛️ Voice Pitch Shift"),
        gr.Radio(choices=["Standard", "Deep Male", "High Female / Kid", "Radio / Telephone"], value="Deep Male", label="🎙️ Voice FX Style"),
        gr.Checkbox(label="🎵 Complete Background Music Removal (Demucs AI)", value=True),
        gr.Checkbox(label="🛡️ Anti-Copyright Shield (H-Flip)", value=True)
    ],
    outputs=[
        gr.Video(label="🎬 Final Processed Video"),
        gr.Textbox(label="Status Window")
    ],
    title="⚡ Studio Ultimate"
)

interface.launch(server_name="0.0.0.0", server_port=7860)
