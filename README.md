import os
import gradio as gr

def process_audio(audio_path):
    if audio_path is None:
        return "Baraye meherbani audio ya video file upload karein."
    return "File process hone ke liye tayar hai!"

with gr.Blocks(title="24/7 Processing Studio") as demo:
    gr.Markdown("# 🎬 Studio App - Audio & Video Processing")
    
    with gr.Row():
        audio_input = gr.Audio(sources=["upload"], type="filepath", label="Upload Audio / Video File")
        output_text = gr.Textbox(label="Processing Output / Status")
    
    process_btn = gr.Button("Start Processing")
    process_btn.click(fn=process_audio, inputs=audio_input, outputs=output_text)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
