import asyncio
import json
import logging
import os
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import gradio as gr
from gradio.components import Component

from src.agent.xiaohongshu.xiaohongshu_agent import XiaohongshuAgent
from src.utils import llm_provider
from src.webui.webui_manager import WebuiManager

logger = logging.getLogger(__name__)


async def _initialize_llm(
    provider: Optional[str],
    model_name: Optional[str],
    temperature: float,
    base_url: Optional[str],
    api_key: Optional[str],
    num_ctx: Optional[int] = None,
):
    """初始化LLM"""
    if not provider or not model_name:
        logger.info("LLM Provider或Model Name未指定")
        return None
    try:
        logger.info(f"初始化LLM: Provider={provider}, Model={model_name}")
        llm = llm_provider.get_llm_model(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            base_url=base_url or None,
            api_key=api_key or None,
            num_ctx=num_ctx if provider == "ollama" else None,
        )
        return llm
    except Exception as e:
        logger.error(f"初始化LLM失败: {e}", exc_info=True)
        gr.Warning(f"初始化LLM失败: {e}")
        return None


def scan_posts_content() -> List[Dict[str, Any]]:
    """扫描发帖内容"""
    posts = []
    
    # 只扫描专门的小红书发帖目录
    scan_dir = "./tmp/xiaohongshu_posts"
    
    if not os.path.exists(scan_dir):
        logger.info(f"创建小红书发帖目录: {scan_dir}")
        os.makedirs(scan_dir, exist_ok=True)
        return posts
        
    logger.info(f"扫描小红书发帖目录: {scan_dir}")
    
    for root, dirs, files in os.walk(scan_dir):
        # 跳过根目录本身
        if root == scan_dir:
            continue
            
        current_post = {
            "title": os.path.basename(root),
            "text_content": "",
            "images": [],
            "source_dir": root
        }
        
        # 扫描文本文件作为文案
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in ['.txt', '.md']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            current_post["text_content"] += content + "\n\n"
                except Exception as e:
                    logger.error(f"读取文本文件 {file_path} 时出错: {e}")
            
            # 扫描图片文件
            elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                current_post["images"].append(file_path)
        
        # 如果有内容或图片，添加到posts列表
        if current_post["text_content"].strip() or current_post["images"]:
            posts.append(current_post)
    
    logger.info(f"扫描到 {len(posts)} 个发帖内容")
    return posts


async def run_xiaohongshu_task(
    webui_manager: WebuiManager, 
    components: Dict[Component, Any]
) -> AsyncGenerator[Dict[Component, Any], None]:
    """运行小红书发帖任务"""
    
    # 获取组件
    start_button_comp = webui_manager.get_component_by_id("xiaohongshu_agent.start_button")
    stop_button_comp = webui_manager.get_component_by_id("xiaohongshu_agent.stop_button")
    output_comp = webui_manager.get_component_by_id("xiaohongshu_agent.output")
    max_posts_comp = webui_manager.get_component_by_id("xiaohongshu_agent.max_posts")
    
    # 获取设置
    max_posts = int(components.get(max_posts_comp, 5))
    
    # 获取LLM设置
    def get_setting(tab: str, key: str, default: Any = None):
        comp = webui_manager.id_to_component.get(f"{tab}.{key}")
        return components.get(comp, default) if comp else default
    
    llm_provider_name = get_setting("agent_settings", "llm_provider")
    llm_model_name = get_setting("agent_settings", "llm_model_name")
    llm_temperature = max(get_setting("agent_settings", "llm_temperature", 0.5), 0.5)
    llm_base_url = get_setting("agent_settings", "llm_base_url")
    llm_api_key = get_setting("agent_settings", "llm_api_key")
    ollama_num_ctx = get_setting("agent_settings", "ollama_num_ctx")
    
    # 获取浏览器设置
    browser_config = {
        "headless": get_setting("browser_settings", "headless", False),
        "disable_security": get_setting("browser_settings", "disable_security", False),
        "browser_binary_path": get_setting("browser_settings", "browser_binary_path"),
        "user_data_dir": get_setting("browser_settings", "browser_user_data_dir"),
        "window_width": int(get_setting("browser_settings", "window_w", 1280)),
        "window_height": int(get_setting("browser_settings", "window_h", 1100)),
    }
    
    # 初始状态更新
    yield {
        start_button_comp: gr.update(value="⏳ 运行中...", interactive=False),
        stop_button_comp: gr.update(interactive=True),
        output_comp: gr.update(value="🚀 开始小红书发帖任务..."),
    }
    
    try:
        # 初始化LLM
        llm = await _initialize_llm(
            llm_provider_name, llm_model_name, llm_temperature, llm_base_url, llm_api_key,
            ollama_num_ctx if llm_provider_name == "ollama" else None
        )
        
        if not llm:
            yield {
                output_comp: gr.update(value="❌ LLM初始化失败，请检查Agent Settings"),
                start_button_comp: gr.update(value="🚀 开始发帖", interactive=True),
                stop_button_comp: gr.update(interactive=False),
            }
            return
        
        # 创建小红书Agent
        xiaohongshu_agent = XiaohongshuAgent(
            llm=llm,
            browser_config=browser_config,
        )
        
        # 运行发帖任务
        yield {
            output_comp: gr.update(value="📱 正在启动小红书发帖..."),
        }
        
        results = await xiaohongshu_agent.run_posting_task(max_posts=max_posts)
        
        # 格式化结果
        output_text = "📊 小红书发帖任务完成\n\n"
        success_count = sum(1 for r in results if r.get("success", False))
        output_text += f"✅ 成功发布: {success_count} 篇\n"
        output_text += f"❌ 失败: {len(results) - success_count} 篇\n\n"
        
        output_text += "详细结果:\n"
        for i, result in enumerate(results, 1):
            if result.get("success", False):
                output_text += f"{i}. ✅ {result.get('post_title', '未知')}\n"
                output_text += f"   内容长度: {len(result.get('content', ''))}\n"
                output_text += f"   图片数量: {result.get('images_count', 0)}\n"
            else:
                output_text += f"{i}. ❌ {result.get('post_title', '未知')}\n"
                error_msg = result.get('error', result.get('message', '未知错误'))
                output_text += f"   错误: {error_msg}\n"
                # 如果是缺少图片的错误，特别标注
                if "不支持发布纯文字帖子" in error_msg:
                    output_text += f"   💡 提示: 请在帖子目录中添加图片文件\n"
            output_text += "\n"
        
        yield {
            output_comp: gr.update(value=output_text),
            start_button_comp: gr.update(value="🚀 开始发帖", interactive=True),
            stop_button_comp: gr.update(interactive=False),
        }
        
    except Exception as e:
        logger.error(f"运行小红书发帖任务失败: {e}", exc_info=True)
        yield {
            output_comp: gr.update(value=f"❌ 任务失败: {str(e)}"),
            start_button_comp: gr.update(value="🚀 开始发帖", interactive=True),
            stop_button_comp: gr.update(interactive=False),
        }


async def stop_xiaohongshu_task(webui_manager: WebuiManager) -> Dict[Component, Any]:
    """停止小红书发帖任务"""
    
    start_button_comp = webui_manager.get_component_by_id("xiaohongshu_agent.start_button")
    stop_button_comp = webui_manager.get_component_by_id("xiaohongshu_agent.stop_button")
    output_comp = webui_manager.get_component_by_id("xiaohongshu_agent.output")
    
    # 这里可以添加停止逻辑
    logger.info("小红书发帖任务已停止")
    
    return {
        output_comp: gr.update(value="⏹️ 小红书发帖任务已停止"),
        start_button_comp: gr.update(value="🚀 开始发帖", interactive=True),
        stop_button_comp: gr.update(interactive=False),
    }


def refresh_posts_content() -> str:
    """刷新发帖内容"""
    try:
        posts = scan_posts_content()
        
        if not posts:
            content_text = "📁 未找到发帖内容\n\n"
            content_text += "请在以下目录创建子目录并放置内容:\n"
            content_text += "• ./tmp/xiaohongshu_posts/ - 小红书专门发帖目录\n\n"
            content_text += "目录结构示例:\n"
            content_text += "• ./tmp/xiaohongshu_posts/帖子1/\n"
            content_text += "  - 文案.txt\n"
            content_text += "  - 图片1.jpg (必需!)\n"
            content_text += "  - 图片2.png (可选)\n\n"
            content_text += "⚠️ 重要提醒:\n"
            content_text += "• 小红书不支持纯文字发布，每个帖子都必须包含至少一张图片\n"
            content_text += "• 没有图片的帖子将无法发布\n\n"
            content_text += "支持的文件格式:\n"
            content_text += "• 文案: .txt, .md\n"
            content_text += "• 图片: .png, .jpg, .jpeg, .gif, .bmp, .webp (必需!)"
        else:
            content_text = f"📁 找到 {len(posts)} 个发帖内容\n\n"
            
            for i, post in enumerate(posts, 1):
                # 检查是否有图片
                has_images = len(post.get('images', [])) > 0
                status = "✅ 可发布" if has_images else "❌ 缺少图片"
                
                content_text += f"{i}. {post['title']} ({status})\n"
                content_text += f"   📝 文案长度: {len(post.get('text_content', ''))}\n"
                content_text += f"   🖼️ 图片数量: {len(post.get('images', []))}\n"
                content_text += f"   📂 来源: {post.get('source_dir', '')}\n"
                
                # 如果没有图片，显示警告
                if not has_images:
                    content_text += f"   ⚠️ 警告: 小红书不支持纯文字发布，此帖子无法发布\n"
                
                # 显示部分内容预览
                if post.get('text_content'):
                    preview = post['text_content'][:100].replace('\n', ' ')
                    if len(post['text_content']) > 100:
                        preview += "..."
                    content_text += f"   内容预览: {preview}\n"
                
                content_text += "\n"
        
        return content_text
        
    except Exception as e:
        logger.error(f"刷新发帖内容失败: {e}", exc_info=True)
        return f"❌ 刷新失败: {str(e)}"


def create_xiaohongshu_agent_tab(webui_manager: WebuiManager):
    """创建小红书发帖Agent的Tab"""
    
    # 存储组件的字典
    components = {}
    
    with gr.Column():
        gr.Markdown(
            """
            # 📱 小红书自动发帖
            ### 从tmp目录读取文案和图片，自动发布到小红书
            """,
            elem_classes=["tab-header-text"],
        )
        
        with gr.Row():
            with gr.Column(scale=2):
                # 设置区域
                with gr.Group():
                    gr.Markdown("⚙️ **发帖设置**")
                    
                    components["max_posts"] = gr.Slider(
                        label="最大发帖数量",
                        minimum=1,
                        maximum=100,
                        value=5,
                        step=1,
                    )
                
                # 内容预览区域
                with gr.Group():
                    gr.Markdown("📁 **发帖内容预览**")
                    
                    components["refresh_button"] = gr.Button("🔄 刷新内容", variant="secondary")
                    
                    components["content_display"] = gr.Textbox(
                        label="发帖内容",
                        lines=10,
                        max_lines=15,
                        show_copy_button=True,
                        interactive=False,
                        placeholder="点击'刷新内容'查看可发布的内容..."
                    )
                
                # 控制按钮
                with gr.Row():
                    components["start_button"] = gr.Button("🚀 开始发帖", variant="primary")
                    components["stop_button"] = gr.Button("⏹️ 停止发帖", variant="stop", interactive=False)
            
            with gr.Column(scale=3):
                # 输出区域
                with gr.Group():
                    gr.Markdown("📊 **运行结果**")
                    
                    components["output"] = gr.Textbox(
                        label="输出",
                        lines=20,
                        max_lines=30,
                        show_copy_button=True,
                        interactive=False,
                        placeholder="点击'开始发帖'开始任务..."
                    )
        
        # 使用说明
        with gr.Accordion("📖 使用说明", open=False):
            gr.Markdown("""
            ### 准备工作
            1. 在tmp目录下准备发帖内容:
               - 文案文件: .txt 或 .md 格式
               - 图片文件: .png, .jpg, .jpeg, .gif, .bmp, .webp 格式 (**必需!**)
            
            2. 支持的目录结构:
               - `./tmp/xiaohongshu_posts/` - 专门的小红书发帖目录
            
            ### ⚠️ 重要限制
            - **小红书不支持纯文字发布**，每个帖子都必须包含至少一张图片
            - 没有图片的内容将无法发布并显示错误
            - 图片是发布成功的必要条件
            
            ### 使用步骤
            1. 点击"刷新内容"查看可发布的内容
            2. 设置最大发帖数量
            3. 点击"开始发帖"开始自动发帖
            4. 系统会自动登录小红书并发布内容
            5. 可随时点击"停止发帖"中止任务
            
            ### 自动清理功能
            - **发布成功后自动删除文件**: 成功发布的帖子目录会被异步删除
            - **防止重复发布**: 已发布的内容不会再次出现在发帖列表中
            - **非阻塞删除**: 删除操作在后台异步执行，不影响发布流程
            - **安全保障**: 只会删除发帖目录下的内容，确保数据安全
            
            ### 注意事项
            - 首次使用需要手动登录小红书
            - 发帖间隔为10秒，避免频率过快
            - 建议先测试少量内容
            - 确保图片文件大小合适（建议小于10MB）
            - 每个帖子目录都必须包含图片文件
            - ⚠️ **重要**: 发布成功的帖子目录会被自动删除，请提前备份重要内容
            """)
    
    # 注册组件
    webui_manager.add_components("xiaohongshu_agent", components)
    
    # 绑定事件
    async def start_wrapper(*args) -> AsyncGenerator[Dict[Component, Any], None]:
        # 构建组件字典
        all_components = webui_manager.get_components()
        components_dict = {}
        for i, comp in enumerate(all_components):
            if i < len(args):
                components_dict[comp] = args[i]
        
        async for result in run_xiaohongshu_task(webui_manager, components_dict):
            yield result
    
    async def stop_wrapper() -> AsyncGenerator[Dict[Component, Any], None]:
        result = await stop_xiaohongshu_task(webui_manager)
        yield result
    
    def refresh_wrapper():
        return refresh_posts_content()
    
    # 绑定按钮事件
    components["start_button"].click(
        fn=start_wrapper,
        inputs=webui_manager.get_components(),
        outputs=webui_manager.get_components(),
    )
    
    components["stop_button"].click(
        fn=stop_wrapper,
        inputs=[],
        outputs=webui_manager.get_components(),
    )
    
    components["refresh_button"].click(
        fn=refresh_wrapper,
        inputs=[],
        outputs=components["content_display"],
    ) 