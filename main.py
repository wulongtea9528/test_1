import gradio as gr
import requests
from bs4 import BeautifulSoup
import re
import os
import argparse
import sys

# 1. 获取当前正在运行的 Python 脚本所在的绝对路径目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2. 将缓存文件夹强制拼接在这个目录下
CACHE_DIR = os.path.join(BASE_DIR, "paper_cache")
# 3. 创建文件夹（如果已存在则跳过）
os.makedirs(CACHE_DIR, exist_ok=True)

def get_real_url(conference, year):
    """智能寻址函数：直接拉取作者的 GitHub README 源码，获取真实链接。"""
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

def get_cache(conference, year):
    """尝试从本地读取缓存文件"""
    cache_path = os.path.join(CACHE_DIR, f"{conference}_{year}.txt")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split('\n', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None, None

def save_cache(conference, year, url, text):
    """将下载的网页文本保存到本地缓存"""
    cache_path = os.path.join(CACHE_DIR, f"{conference}_{year}.txt")
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(f"{url}\n{text}")

# --- 新增：核心数据获取函数（CLI和GUI共用） ---
def fetch_paper_data(conference, year):
    """返回 (target_url, clean_text, is_cached, error_msg)"""
    target_url, clean_text = get_cache(conference, year)
    is_cached = True
    error_msg = None

    if not clean_text:
        is_cached = False
        target_url = get_real_url(conference, year)
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(target_url, headers=headers)
            
            if response.status_code == 404:
                error_msg = f"抱歉，未能找到 {conference} {year} 的数据！页面返回了 404 错误。\n尝试的网址: {target_url}"
                return target_url, "", is_cached, error_msg

            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            clean_text = soup.get_text()
            save_cache(conference, year, target_url, clean_text)
        except Exception as e:
            error_msg = f"拉取网页数据失败: {e}"
            
    return target_url, clean_text, is_cached, error_msg

# --- GUI Web端检索函数 ---
def search_papers(kw1, kw2, kw3, conference, year):
    if not conference or not year:
        return "<p style='color:red;'>请选择或输入会议名称和年份。</p>"

    target_url, clean_text, is_cached, error_msg = fetch_paper_data(conference, year)
    
    if error_msg:
        # 先在外面把换行符替换好，避开 f-string 内部的反斜杠限制
        html_error = error_msg.replace('\n', '<br>')
        
        return f"""
        <div style='padding: 15px; background-color: #ffebe9; color: #cf222e; border: 1px solid #ff8182; border-radius: 6px;'>
            <b>{html_error}</b>
        </div>
        """

    raw_keywords = [kw1, kw2, kw3]
    keywords = [k.strip().lower() for k in raw_keywords if k and k.strip()]
    blocks = re.split(r'(?i)\n(?=paperid:\s*\d+)', clean_text.strip())

    results_html = ""
    count = 0

    for block in blocks:
        if "paperid:" not in block.lower():
            continue

        block_lower = block.lower()
        if not all(kw in block_lower for kw in keywords):
            continue

        count += 1
        block_content = re.sub(r'\s*\n\s*', '\n', block.strip())
        block_content = re.sub(
            r'(?i)(Abstract:)(.*)',
            lambda m: m.group(1) + " " + re.sub(r'\s+', ' ', m.group(2)).strip(),
            block_content,
            flags=re.DOTALL
        )
        block_content = re.sub(
            r'(https?://[^\s]+)',
            r'<a href="\1" target="_blank" style="color: #0366d6; text-decoration: none;">\1</a>',
            block_content
        )
        block_content = block_content.replace('\n', '<br>')
        block_content = re.sub(
            r'(?i)(?:<br>)*(Title:.*?)(?:<br>)*(?=Abstract:|$)',
            r'<div style="font-size: 1.15em; font-weight: bold; margin: 12px 0 8px 0; color: #1f2328;">\1</div>',
            block_content,
            flags=re.DOTALL
        )
        block_content = re.sub(r'(?i)(Abstract:)', r'<b>\1</b>', block_content)

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
    cache_badge = "<span style='margin-left: 10px; background-color: #d4edda; color: #155724; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; vertical-align: middle;'>⚡ 已使用本地缓存</span>" if is_cached else ""

    if count == 0:
        return f"<p>在 <b><a href='{target_url}' target='_blank' style='color: #0366d6; text-decoration: none;'>{conference} {year}</a></b> 中未找到同时包含 <b>'{query_display}'</b> 的相关论文。{cache_badge}</p>"

    return f"<h3 style='display: flex; align-items: center; flex-wrap: wrap;'>🔍 为你在 <a href='{target_url}' target='_blank' style='color: #0366d6; text-decoration: none; margin: 0 5px;'>{conference} {year}</a> 中找到 {count} 篇包含 '{query_display}' 的相关论文：{cache_badge}</h3>" + results_html

# --- 新增：CLI 命令行终端检索函数 ---
def cli_search(keywords, conference, year):
    target_url, clean_text, is_cached, error_msg = fetch_paper_data(conference, year)
    
    if error_msg:
        print(f"\n[错误] {error_msg}\n")
        return

    keywords = [k.strip().lower() for k in keywords if k.strip()]
    blocks = re.split(r'(?i)\n(?=paperid:\s*\d+)', clean_text.strip())
    
    matched_papers = []
    for block in blocks:
        if "paperid:" not in block.lower():
            continue
        
        if all(kw in block.lower() for kw in keywords):
            # 压缩多余的换行和格式
            block_content = re.sub(r'\s*\n\s*', '\n', block.strip())
            block_content = re.sub(
                r'(?i)(Abstract:)(.*)',
                lambda m: m.group(1) + " " + re.sub(r'\s+', ' ', m.group(2)).strip(),
                block_content,
                flags=re.DOTALL
            )
            matched_papers.append(block_content)

    query_display = " + ".join(keywords) if keywords else "无(显示所有)"
    print(f"\n{'[⚡ 使用缓存]' if is_cached else '[🌐 网络拉取]'} 目标: {conference} {year}")
    print(f"🔗 链接: {target_url}")
    print(f"🔍 关键词: {query_display}")
    print(f"📄 找到相关论文: {len(matched_papers)} 篇\n")
    print("=" * 60)

    for i, paper in enumerate(matched_papers, 1):
        print(f"\n[{i}/{len(matched_papers)}] \n{paper}\n")
        print("-" * 60)


# --------- GUI 界面设计 ---------
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

# --------- 主程序入口（路由分配） ---------
if __name__ == "__main__":
    # 配置命令行参数解析
    parser = argparse.ArgumentParser(description="AI 顶会论文快速检索工具 (支持网页UI与命令行CLI)")
    parser.add_argument("-r", "--retrieve", nargs='+', help="检索的关键词，可以输入多个，例如: -r graph learning")
    parser.add_argument("-c", "--conference", default="AAAI", help="会议名称 (默认: AAAI)")
    parser.add_argument("-y", "--year", default="2025", help="会议年份 (默认: 2025)")
    
    # 判断是否传入了任何参数 (sys.argv[0] 是脚本名称，>1说明带了参数)
    if len(sys.argv) > 1:
        args = parser.parse_args()
        # 如果用户加了参数，则执行 CLI 命令行模式
        keywords = args.retrieve if args.retrieve else []
        cli_search(keywords, args.conference, args.year)
    else:
        # 如果什么参数都没加 (例如直接双击运行，或仅仅输入 python paper.py)，则启动 GUI 网页模式
        demo.launch(inbrowser=True)