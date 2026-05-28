import gradio as gr
import os
from pathlib import Path
import fitz
from docx import Document
from main import run


def parse_upload_file(file_path):
    """读取上传的文件并提取文本内容，支持PDF/DOCX/MD/TXT四种格式"""
    if not file_path or not os.path.exists(file_path):
        return ""
    suffix = Path(file_path).suffix.lower()
    content = ""
    if suffix == ".pdf":
        # PDF使用PyMuPDF（fitz）解析
        doc = fitz.open(file_path)
        for page in doc:
            content += page.get_text()
    elif suffix == ".docx":
        # DOCX使用python-docx解析段落文本
        doc = Document(file_path)
        content = "\n".join([p.text for p in doc.paragraphs])
    elif suffix in [".md", ".txt"]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    return content.strip()

def start_pipeline(upload_file, prd_text, data_source_type=None):
    """组装多源需求输入并启动流水线"""
    # 融合：数据源标识 + 上传文档 + 手动需求 三项合一为最终PRD
    file_content = parse_upload_file(upload_file) if upload_file else ""
    final_prd = f"【上传文档内容】\n{file_content}\n【手动补充需求】\n{prd_text}"
    result = run(user_prd=final_prd)
    return result.raw

with gr.Blocks(title="Spark大数据AI研发平台") as demo:
    gr.Markdown("""
    # Spark全链路多智能体协同研发平台【生产级】
    支持：PDF/DOCX/MD/TXT 需求文档上传 | Hive/HDFS数据源 | 8步工作流 + 3道人工审批Gate
    """)
    gr.Divider()

    upload_file = gr.File(
        label="上传PRD需求文档",
        file_types=[".pdf", ".docx", ".md", ".txt"]
    )

    prd_text = gr.Textbox(label="手动补充业务需求", lines=12)

    gr.Divider()
    submit_btn = gr.Button("启动全链路智能研发", variant="primary", size="large")
    output_result = gr.Textbox(label="全链路交付成果", lines=40, show_copy_button=True)

    submit_btn.click(
        fn=start_pipeline,
        inputs=[upload_file, prd_text],
        outputs=[output_result]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7862, inbrowser=True)
