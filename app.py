import os
import re
import shutil
import subprocess
import gradio as gr
from faster_whisper import WhisperModel
import arabic_reshaper
from bidi.algorithm import get_display

# Optimized Whisper model for extreme CPU speed
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=4)

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

def process_master_studio(video_input, target_language, font_size, text_color, pitch_level, voice_effect, remove_music, enable_copyright_shield):
    try:
        if video_input is None:
            return None, "Error: Video upload karein!"

        raw_input = "raw_input_video.mp4"
        shutil.copy(video_input, raw_input)

        # 1. High-Speed Audio Extraction
        raw_audio = "extracted_speech.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_input,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            raw_audio
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Aggressive Background Music & Noise Cut Filter
        cleaned_audio = raw_audio
        if remove_music:
            cleaned_audio = "voice_isolated.wav"
            subprocess.run([
                "ffmpeg", "-y", "-i", raw_audio,
                "-af", "highpass=f=200,lowpass=f=3000,afftdn=nr=25:nf=-40:tn=1",
                cleaned_audio
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Fast Voice Changer Effects
        final_audio = "processed_final_audio.wav"
        pitch_rate = str(int(16000 * pitch_level))
        tempo_rate = str(round(1.0 / pitch_level, 3))
        
        audio_filters = [f"asetrate={pitch_rate}", f"atempo={tempo_rate}"]
        
        if voice_effect == "Deep Male":
            audio_filters.append("equalizer=f=100:width_type=h:width=200:g=8,bass=g=6")
        elif voice_effect == "High Female / Kid":
            audio_filters.append("equalizer=f=3000:width_type=h:width=1000:g=6,treble=g=5")
        elif voice_effect == "Radio / Telephone":
            audio_filters.append("highpass=f=400,lowpass=f=2600")
            
        af_chain = ",".join(audio_filters)
        
        subprocess.run([
            "ffmpeg", "-y", "-i", cleaned_audio,
            "-af", af_chain,
            final_audio
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. Ultra-Fast Transcription Execution
        selected_lang = LANGUAGE_DICT.get(target_language, "en")
        task_type = "translate" if selected_lang == "en" else "transcribe"
        
        segments, _ = whisper_model.transcribe(
            cleaned_audio,
            task=task_type,
            language=None if task_type == "translate" else selected_lang,
            beam_size=1,
            best_of=1,
            temperature=0,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            word_timestamps=False
        )

        # 5. Bottom Captions Formatting
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
Style: DefaultStyle,Sans,{font_size},{primary_color},&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,2,1,2,10,10,25,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        with open(ass_path, "w", encoding="utf-8-sig") as f:
            f.write(ass_header)
            for segment in segments:
                start_time, end_time, speech_text = segment.start, segment.end, segment.text.strip()
                formatted_dialogue = fix_rtl_script(speech_text, selected_lang)
                if not formatted_dialogue:
                    continue

                def convert_time(seconds):
                    h, m, sec, ms = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60), int((seconds % 1) * 100)
                    return f"{h}:{m:02d}:{sec:02d}.{ms:02d}"

                f.write(f"Dialogue: 0,{convert_time(start_time)},{convert_time(end_time)},DefaultStyle,,0,0,0,,{formatted_dialogue}\n")

        # 6. Ultrafast Video Transcoding Output
        video_filters = []
        if enable_copyright_shield:
            video_filters.append("hflip")

        video_filters.append(f"ass={ass_path}")
        vf_chain = ",".join(video_filters)

        final_video = "final_output_video.mp4"
        ffmpeg_render = [
            "ffmpeg", "-y",
            "-i", raw_input,
            "-i", final_audio,
            "-vf", vf_chain,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", "32",
            "-c:a", "aac",
            "-b:a", "64k",
            final_video
        ]
        subprocess.run(ffmpeg_render, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return final_video, "⚡ Ultra-Fast Processing Complete!"

    except Exception as e:
        return None, f"Error: {str(e)}"

# Gradio Interface
with gr.Blocks(title="⚡ Fast Studio Ultimate") as demo:
    gr.Markdown("# ⚡ High-Speed Studio App")
    with gr.Row():
        with gr.Column():
            video_in = gr.Video(label="📹 Upload Video")
            target_lang = gr.Dropdown(choices=list(LANGUAGE_DICT.keys()), value="English", label="🌐 Subtitle Language")
            font_sz = gr.Slider(minimum=12, maximum=32, step=1, value=18, label="🔤 Font Size")
            txt_clr = gr.Radio(choices=["Yellow", "White", "Green", "Cyan"], value="Yellow", label="🎨 Caption Color")
            pitch_st = gr.Slider(minimum=0.70, maximum=1.30, step=0.02, value=0.88, label="🎛️ Pitch Shift")
            v_style = gr.Radio(choices=["Standard", "Deep Male", "High Female / Kid", "Radio / Telephone"], value="Deep Male", label="🎙️ Voice FX")
            rem_mus = gr.Checkbox(label="🎵 Heavy Music & Noise Removal", value=True)
            c_shield = gr.Checkbox(label="🛡️ Anti-Copyright Shield", value=True)
            submit_btn = gr.Button("🚀 Start Fast Processing")
        
        with gr.Column():
            video_out = gr.Video(label="🎬 Processed Video")
            status_out = gr.Textbox(label="Status Window")

    submit_btn.click(
        fn=process_master_studio,
        inputs=[video_in, target_lang, font_sz, txt_clr, pitch_st, v_style, rem_mus, c_shield],
        outputs=[video_out, status_out]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
