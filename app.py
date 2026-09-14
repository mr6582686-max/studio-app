import os
import gradio as gr

def process_audio(file_path):
    if file_path is None:
        return "Baraye meherbani audio ya video file upload karein."
    return f"File successfully receive ho gayi hai: {os.path.basename(file_path)}"

with gr.Blocks(title="24/7 Processing Studio") as demo:
    gr.Markdown("# 🎬 Studio App - Audio & Video Processing")
    
    with gr.Row():
        file_input = gr.File(label="Upload Audio or Video File (.mp4, .mp3, .wav)", file_count="single")
        output_text = gr.Textbox(label="Processing Output / Status")
    
    process_btn = gr.Button("Start Processing")
    process_btn.click(fn=process_audio, inputs=file_input, outputs=output_text)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
