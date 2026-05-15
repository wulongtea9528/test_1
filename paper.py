import gradio as gr
import requests
from bs4 import BeautifulSoup
import re


def search_papers(query):
    if not query.strip():
        return "<p style='color:red;'>请输入查询词。</p>"

    url = "https://hongsong-wang.github.io/ICML2026/"

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        clean_text = soup.get_text()

    except Exception as e:
        return f"<p style='color:red;'>拉取网页数据失败: {e}</p>"

    # 兼容不同大小写的 PaperID 划分块
    blocks = re.split(r'\n(?=(?i)paperid:\s*\d+)', clean_text.strip())

    results_html = ""
    count = 0

    for block in blocks:
        if query.lower() in block.lower() and "paperid:" in block.lower():
            count += 1

            # 1. 处理链接：转为可点击的 HTML 链接
            block_content = re.sub(
                r'(https?://[^\s]+)',
                r'<a href="\1" target="_blank" style="color: #0366d6; text-decoration: none;">\1</a>',
                block
            )

            # 2. 【核心修改】：将 Title 单独一行并加粗
            # 逻辑：匹配 Title: 开头到 Abstract: 之前的所有内容
            block_content = re.sub(
                r'((?i)Title:.*?)(?=(?i)Abstract:|$)',
                r'<br><b style="font-size: 1.1em; display: block; margin: 10px 0;">\1</b>',
                block_content,
                flags=re.DOTALL
            )

            # 3. 处理换行符，让显示更自然
            block_content = block_content.replace('\n', '<br>')

            # 4. 高亮搜索关键词
            insensitive_query = re.compile(re.escape(query), re.IGNORECASE)
            block_content = insensitive_query.sub(
                lambda m: f"<span style='background-color: #ffeebf; font-weight: bold;'>{m.group(0)}</span>",
                block_content
            )

            # 包装到卡片中
            results_html += f"""
            <div style='border: 1px solid #e1e4e8; padding: 20px; margin-bottom: 20px; border-radius: 8px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                <div style='font-family: -apple-system, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #24292e;'>
                    {block_content}
                </div>
            </div>
            """

    if count == 0:
        return f"<p>未找到包含 <b>'{query}'</b> 的相关论文。</p>"

    return f"<h3>🔍 为你找到 {count} 篇相关论文：</h3>" + results_html


# Gradio UI 部分保持不变
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 📚 ICML 2026 论文快速检索工具")

    with gr.Row():
        query_input = gr.Textbox(
            label="搜索方向（支持大小写模糊匹配）",
            placeholder="例如: Sheaf Neural Network...",
            scale=4
        )
        search_btn = gr.Button("开始检索", variant="primary", scale=1)

    output_html = gr.HTML()

    search_btn.click(fn=search_papers, inputs=query_input, outputs=output_html)
    query_input.submit(fn=search_papers, inputs=query_input, outputs=output_html)

if __name__ == "__main__":
    demo.launch(inbrowser=True)