import gradio as gr
import requests
from bs4 import BeautifulSoup
import re


def get_real_url(conference, year):
    """
    智能寻址函数：直接拉取作者的 GitHub README 源码，
    通过模糊匹配找到真正的会议链接，无视他奇葩的后缀命名。
    """
    conf_str = str(conference).strip().lower()
    if conf_str == "neurips":
        conf_str = "nips"  # 兼容作者的老习惯
    year_str = str(year).strip()

    # 尝试拉取作者的 README 文件（兼容 main 和 master 分支）
    for branch in ['main', 'master']:
        readme_url = f"https://raw.githubusercontent.com/hongsong-wang/CV_Paper_Portal/{branch}/README.md"
        try:
            response = requests.get(readme_url, timeout=5)
            if response.status_code == 200:
                # 使用正则提取 README 中所有指向他 github.io 的链接
                # 匹配格式如：https://hongsong-wang.github.io/AAAI2025_ABSTRACT-/
                links = re.findall(r'https://hongsong-wang\.github\.io/[^\s\)]+', response.text)

                # 在这些真实链接中进行模糊匹配
                for link in links:
                    if conf_str in link.lower() and year_str in link:
                        return link  # 找到了！直接返回这个绝对正确的真实链接
        except Exception:
            continue

    # 如果 README 里没找到，或者网络出问题，返回兜底的标准预测链接
    return f"https://hongsong-wang.github.io/{conference.upper()}{year}/"


def search_papers(query, conference, year):
    if not query.strip():
        return "<p style='color:red;'>请输入查询词。</p>"
    if not conference or not year:
        return "<p style='color:red;'>请选择或输入会议名称和年份。</p>"

    # --- 【终极优化：直接获取真实链接】 ---
    target_url = get_real_url(conference, year)
    # -------------------------------------

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(target_url, headers=headers)

        if response.status_code == 404:
            return f"""
            <div style='padding: 15px; background-color: #ffebe9; color: #cf222e; border: 1px solid #ff8182; border-radius: 6px;'>
                <b>抱歉，未能找到 {conference} {year} 的数据！</b><br><br>
                系统尝试访问的真实网址是：<a href="{target_url}" target="_blank" style="color: #cf222e; text-decoration: underline;">{target_url}</a><br>
                该页面返回了 404 错误。说明作者的项目主页里暂时没有这个会议的有效链接。
            </div>
            """

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

            block_content = re.sub(
                r'(https?://[^\s]+)',
                r'<a href="\1" target="_blank" style="color: #0366d6; text-decoration: none;">\1</a>',
                block
            )

            block_content = re.sub(
                r'((?i)Title:.*?)(?=(?i)Abstract:|$)',
                r'<b style="font-size: 1.1em;">\1</b>',
                block_content,
                flags=re.DOTALL
            )

            block_content = block_content.replace('\n', '<br>')

            insensitive_query = re.compile(re.escape(query), re.IGNORECASE)
            block_content = insensitive_query.sub(
                lambda m: f"<span style='background-color: #ffeebf; font-weight: bold;'>{m.group(0)}</span>",
                block_content
            )

            results_html += f"""
            <div style='border: 1px solid #e1e4e8; padding: 20px; margin-bottom: 20px; border-radius: 8px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                <div style='font-family: -apple-system, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #24292e;'>
                    {block_content}
                </div>
            </div>
            """

    if count == 0:
        return f"<p>在 <b><a href='{target_url}' target='_blank' style='color: #0366d6; text-decoration: none;'>{conference} {year}</a></b> 中未找到包含 <b>'{query}'</b> 的相关论文。</p>"

    return f"<h3>🔍 为你在 <a href='{target_url}' target='_blank' style='color: #0366d6; text-decoration: none;'>{conference} {year}</a> 中找到 {count} 篇相关论文：</h3>" + results_html


# --------- UI 界面设计 ---------
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 📚 AI 顶会论文快速检索工具")
    gr.Markdown("基于 Hongsong Wang 的公开 GitHub Pages 数据。")

    with gr.Row():
        conf_input = gr.Dropdown(
            choices=["CVPR", "ICCV", "ECCV", "NeurIPS", "ICML", "ICLR", "AAAI", "IJCAI"],
            value="AAAI",
            label="选择或手动输入会议",
            allow_custom_value=True,
            scale=1
        )

        year_input = gr.Dropdown(
            choices=["2024", "2025", "2026", "2027"],
            value="2025",
            label="选择或手动输入年份",
            allow_custom_value=True,
            scale=1
        )

    with gr.Row():
        query_input = gr.Textbox(
            label="搜索方向（支持大小写模糊匹配）",
            placeholder="例如: Sheaf Neural Network, Graph...",
            scale=4
        )
        search_btn = gr.Button("开始检索", variant="primary", scale=1)

    output_html = gr.HTML()

    search_btn.click(fn=search_papers, inputs=[query_input, conf_input, year_input], outputs=output_html)
    query_input.submit(fn=search_papers, inputs=[query_input, conf_input, year_input], outputs=output_html)

if __name__ == "__main__":
    demo.launch(inbrowser=True)