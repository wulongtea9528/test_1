import gradio as gr
import requests
from bs4 import BeautifulSoup
import re
import os

# 1. 获取当前正在运行的 Python 脚本 (paper.py) 所在的绝对路径目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2. 将缓存文件夹强制拼接在这个目录下
CACHE_DIR = os.path.join(BASE_DIR, "paper_cache")
# 3. 创建文件夹（如果已存在则跳过）
os.makedirs(CACHE_DIR, exist_ok=True)

def get_real_url(conference, year):
    """
    智能寻址函数：直接拉取作者的 GitHub README 源码，获取真实链接。
    """
    conf_str = str(conference).strip().lower()
    if conf_str == "neurips":
        conf_str = "nips"
    year_str = str(year).strip()

    for branch in ['main', 'master']:
        readme_url = f"https://raw.githubusercontent.com/hongsong-wang/CV_Paper_Portal/{branch}/README.md"
        try:
            response = requests.get(readme_url, timeout=5)
            if response.status_code == 200:
                links = re.findall(r'https://hongsong-wang\.github\.io/[^\s\)]+', response.text)
                for link in links:
                    if conf_str in link.lower() and year_str in link:
                        return link
        except Exception:
            continue

    return f"https://hongsong-wang.github.io/{conference.upper()}{year}/"


# --- 新增：读取和写入缓存的辅助函数 ---
def get_cache(conference, year):
    """尝试从本地读取缓存文件"""
    cache_path = os.path.join(CACHE_DIR, f"{conference}_{year}.txt")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 约定格式：第一行存放目标网址，剩余内容存放网页文本
        parts = content.split('\n', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None, None


def save_cache(conference, year, url, text):
    """将下载的网页文本保存到本地缓存"""
    cache_path = os.path.join(CACHE_DIR, f"{conference}_{year}.txt")
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(f"{url}\n{text}")


def search_papers(kw1, kw2, kw3, conference, year):
    if not conference or not year:
        return "<p style='color:red;'>请选择或输入会议名称和年份。</p>"

    # --- 新增：尝试读取缓存 ---
    target_url, clean_text = get_cache(conference, year)
    is_cached = True

    if not clean_text:
        is_cached = False
        # 如果没有缓存，则进行漫长的网络请求
        target_url = get_real_url(conference, year)

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

            # --- 新增：成功拉取后，保存到本地供下次使用 ---
            save_cache(conference, year, target_url, clean_text)

        except Exception as e:
            return f"<p style='color:red;'>拉取网页数据失败: {e}</p>"

    # --- 【UI 升级适配：收集多个框的关键词】 ---
    raw_keywords = [kw1, kw2, kw3]
    keywords = [k.strip().lower() for k in raw_keywords if k and k.strip()]
    # ----------------------------------------

    blocks = re.split(r'(?i)\n(?=paperid:\s*\d+)', clean_text.strip())

    results_html = ""
    count = 0

    for block in blocks:
        if "paperid:" not in block.lower():
            continue

        # 判断是否包含所有已填写的关键词
        block_lower = block.lower()
        match_all = True
        for kw in keywords:
            if kw not in block_lower:
                match_all = False
                break

        if not match_all:
            continue

        count += 1

        # --- 【优化文本排版】 ---
        # 1. 终极压缩：将包含空格的连续多余空行，强制压缩为一个干净的换行符
        block_content = re.sub(r'\s*\n\s*', '\n', block.strip())

        # 2. 【新增】修复 Abstract 碎行问题：将 Abstract 后面的所有换行和连续空格，压扁为一个单空格
        block_content = re.sub(
            r'(?i)(Abstract:)(.*)',
            lambda m: m.group(1) + " " + re.sub(r'\s+', ' ', m.group(2)).strip(),
            block_content,
            flags=re.DOTALL
        )

        # 3. 处理链接 (转为可点击)
        block_content = re.sub(
            r'(https?://[^\s]+)',
            r'<a href="\1" target="_blank" style="color: #0366d6; text-decoration: none;">\1</a>',
            block_content
        )

        # 4. 将剩余文本的单换行替换为网页换行符 <br>
        block_content = block_content.replace('\n', '<br>')

        # 5. 精确控制间距：吃掉 Title 前后多余的 <br>，完全交由 margin 控制 (上间距 12px，下间距 8px)
        block_content = re.sub(
            r'(?i)(?:<br>)*(Title:.*?)(?:<br>)*(?=Abstract:|$)',
            r'<div style="font-size: 1.15em; font-weight: bold; margin: 12px 0 8px 0; color: #1f2328;">\1</div>',
            block_content,
            flags=re.DOTALL
        )

        # 6. 可选美化：把 Abstract: 这几个前缀字稍微加粗，层级更清晰
        block_content = re.sub(r'(?i)(Abstract:)', r'<b>\1</b>', block_content)

        # 7. 高亮所有有效关键词
        for kw in keywords:
            insensitive_query = re.compile(re.escape(kw), re.IGNORECASE)
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

    query_display = " + ".join(keywords) if keywords else "所有论文"

    # --- 新增：若触发缓存，则展示缓存徽章提醒用户 ---
    cache_badge = "<span style='margin-left: 10px; background-color: #d4edda; color: #155724; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; vertical-align: middle;'>⚡ 已使用本地缓存</span>" if is_cached else ""

    if count == 0:
        return f"<p>在 <b><a href='{target_url}' target='_blank' style='color: #0366d6; text-decoration: none;'>{conference} {year}</a></b> 中未找到同时包含 <b>'{query_display}'</b> 的相关论文。{cache_badge}</p>"

    return f"<h3 style='display: flex; align-items: center; flex-wrap: wrap;'>🔍 为你在 <a href='{target_url}' target='_blank' style='color: #0366d6; text-decoration: none; margin: 0 5px;'>{conference} {year}</a> 中找到 {count} 篇包含 '{query_display}' 的相关论文：{cache_badge}</h3>" + results_html


# --------- UI 界面设计 ---------
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 📚 AI 顶会论文快速检索工具")
    gr.Markdown("基于 Hongsong Wang 的公开 GitHub Pages 数据。首次搜索某会议会自动下载数据，后续搜索**秒出结果**。")

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

    gr.Markdown("### 🔍 联合检索条件 (填写多个框表示同时包含，留空则忽略该条件，全空显示所有)")
    with gr.Row():
        kw1 = gr.Textbox(label="关键词 1", placeholder="例如: graph", scale=1)
        kw2 = gr.Textbox(label="关键词 2 (可选)", placeholder="例如: tabular", scale=1)
        kw3 = gr.Textbox(label="关键词 3 (可选)", placeholder="例如: learning", scale=1)

        search_btn = gr.Button("开始检索", variant="primary", scale=1)

    output_html = gr.HTML()

    inputs_list = [kw1, kw2, kw3, conf_input, year_input]

    search_btn.click(fn=search_papers, inputs=inputs_list, outputs=output_html)

    kw1.submit(fn=search_papers, inputs=inputs_list, outputs=output_html)
    kw2.submit(fn=search_papers, inputs=inputs_list, outputs=output_html)
    kw3.submit(fn=search_papers, inputs=inputs_list, outputs=output_html)

if __name__ == "__main__":
    demo.launch(inbrowser=True)