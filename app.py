import os
import re
import shutil
import subprocess
import gradio as gr
from faster_whisper import WhisperModel
import arabic_reshaper
from bidi.algorithm import get_display

# Light & Fast Whisper Model
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

def process_clean_fast_video(video_input, target_language, font_size, remove_music):
    try:
        if video_input is None:
            return None, "Error: Pehle video upload karein!"

        raw_input = "raw_input_video.mp4"
        shutil.copy(video_input, raw_input)

        # 1. Fast Audio Extraction
        raw_audio = "extracted_speech.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_input,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            raw_audio
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Aggressive Background Music Filter
        cleaned_audio = raw_audio
        if remove_music:
            cleaned_audio = "voice_isolated.wav"
            # Bandpass + FFT Noise suppressor + Dynamic Compand for voice isolation
            subprocess.run([
                "ffmpeg", "-y", "-i", raw_audio,
                "-af", "highpass=f=250,lowpass=f=3200,afftdn=nr=30:nf=-50:tn=1,compand=attacks=0:decays=0.08:points=-80/-80|-40/-10|0/0",
                cleaned_audio
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. High Accuracy & Fast Caption Detection
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

        # 4. ASS Subtitles Formatting (Bottom Center Alignment)
        ass_path = "output_subtitles.ass"
        ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: DefaultStyle,Sans,{font_size},&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,2,1,2,10,10,20,1

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

        # 5. Super Fast Video Encoding (Ultrafast Preset)
        final_video = "final_output_video.mp4"
        ffmpeg_render = [
            "ffmpeg", "-y",
            "-i", raw_input,
            "-i", cleaned_audio,
            "-vf", f"ass={ass_path}",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", "30",
            "-c:a", "aac",
            "-b:a", "96k",
            final_video
        ]
        subprocess.run(ffmpeg_render, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return final_video, "🚀 Fast Processing Complete!"

    except Exception as e:
        return None, f"Error: {str(e)}"

# Minimal & Clean Interface
with gr.Blocks(title="⚡ Fast Subtitle & Music Remover") as demo:
    gr.Markdown("# ⚡ Fast Video Processor (Captions + Music Remover)")
    
    with gr.Row():
        with gr.Column():
            video_in = gr.Video(label="📹 Upload Video")
            target_lang = gr.Dropdown(choices=list(LANGUAGE_DICT.keys()), value="English", label="🌐 Subtitle Language")
            font_sz = gr.Slider(minimum=12, maximum=32, step=1, value=18, label="🔤 Font Size")
            rem_mus = gr.Checkbox(label="🎵 Remove Background Music completely", value=True)
            submit_btn = gr.Button("🚀 Start Fast Processing")
        
        with gr.Column():
            video_out = gr.Video(label="🎬 Processed Output")
            status_out = gr.Textbox(label="Status Window")

    submit_btn.click(
        fn=process_clean_fast_video,
        inputs=[video_in, target_lang, font_sz, rem_mus],
        outputs=[video_out, status_out]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    demo.launch(server_name="0.0.0.0", server_port=port)
