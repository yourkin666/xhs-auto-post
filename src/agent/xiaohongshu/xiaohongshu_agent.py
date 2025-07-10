import asyncio
import json
import logging
import os
import shutil
import signal
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from browser_use.agent.service import Agent
from browser_use.agent.views import AgentHistoryList
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from browser_use.utils import time_execution_async
from langchain_core.language_models.chat_models import BaseChatModel

from src.browser.custom_browser import CustomBrowser
from src.controller.custom_controller import CustomController
from .xiaohongshu_login_config import XiaohongshuLoginConfig
from .cookie_manager import XiaohongshuCookieManager

logger = logging.getLogger(__name__)


class XiaohongshuAgent:
    """小红书自动发帖Agent"""
    
    def __init__(
        self,
        llm: BaseChatModel,
        browser_config: Dict[str, Any],
        posts_dir: str = "./tmp/xiaohongshu_posts",
    ):
        """
        初始化小红书发帖Agent
        
        Args:
            llm: 语言模型
            browser_config: 浏览器配置
            posts_dir: 发帖内容目录
        """
        self.llm = llm
        self.browser_config = browser_config
        self.posts_dir = Path(posts_dir)
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        
        # 动态扫描可用的内容文件
        self.available_posts = self._scan_available_posts()
        
        self.browser = None
        self.browser_context = None
        self.controller: Optional[CustomController] = None
        self.current_task_id = None
        
        # Cookie管理器
        self.cookie_manager = XiaohongshuCookieManager()
        self.use_cookie_login = browser_config.get("use_cookie_login", True)
        self.cookie_file_path = browser_config.get("cookie_file_path", "")
        
        # 状态管理
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False
        
        # 注册信号处理器
        self._register_signal_handlers()
        
        logger.info(f"🎯 小红书发帖Agent初始化完成")
        logger.info(f"📁 发帖目录: {self.posts_dir}")
        logger.info(f"📊 找到 {len(self.available_posts)} 个可用的发布内容")
        
        if self.available_posts:
            for i, post in enumerate(self.available_posts[:3], 1):
                title = post.get('title', 'untitled')
                images = len(post.get('images', []))
                text_len = len(post.get('text_content', ''))
                logger.info(f"  {i}. {title} ({images}张图片, {text_len}字文案)")
            
            if len(self.available_posts) > 3:
                logger.info(f"  ... 还有 {len(self.available_posts) - 3} 个内容")
        else:
            logger.warning("⚠️ 未找到发布内容，请将内容放到发帖目录中")
    
    async def setup_browser(self) -> None:
        """设置浏览器"""
        if self.browser is not None:
            return
            
        # 🔧 关键修复：如果已经请求停止，不允许重新创建浏览器
        if self.stop_requested:
            logger.info("🛑 任务已停止，不允许重新创建浏览器")
            return
            
        # 使用优化的配置
        optimized_config = XiaohongshuLoginConfig.get_browser_config()
        
        # 合并用户配置和优化配置
        headless = self.browser_config.get("headless", optimized_config.get("headless", False))
        window_w = self.browser_config.get("window_width", optimized_config.get("window_width", 1280))
        window_h = self.browser_config.get("window_height", optimized_config.get("window_height", 720))
        browser_user_data_dir = self.browser_config.get("user_data_dir", None)
        use_own_browser = self.browser_config.get("use_own_browser", False)
        browser_binary_path = self.browser_config.get("browser_binary_path", None)
        wss_url = self.browser_config.get("wss_url", None)
        cdp_url = self.browser_config.get("cdp_url", None)
        
        # 使用优化的浏览器参数
        extra_args = optimized_config.get("extra_browser_args", [])
        
        if use_own_browser:
            browser_binary_path = os.getenv("BROWSER_PATH", None) or browser_binary_path
            if browser_binary_path == "":
                browser_binary_path = None
            browser_user_data = browser_user_data_dir or os.getenv("BROWSER_USER_DATA", None)
            if browser_user_data:
                extra_args += [f"--user-data-dir={browser_user_data}"]
        else:
            browser_binary_path = None
            
        self.browser = CustomBrowser(
            config=BrowserConfig(
                headless=headless,
                browser_binary_path=browser_binary_path,
                extra_browser_args=extra_args,
                disable_security=optimized_config.get("disable_security", True),
                wss_url=wss_url,
                cdp_url=cdp_url,
                new_context_config=BrowserContextConfig(
                    window_width=window_w,
                    window_height=window_h,
                )
            )
        )
        
        context_config = BrowserContextConfig(
            save_downloads_path="./tmp/downloads",
            window_height=window_h,
            window_width=window_w,
            force_new_context=True,
            user_agent=optimized_config.get("user_agent", ""),
            minimum_wait_page_load_time=1.0,
            wait_for_network_idle_page_load_time=2.0,
            maximum_wait_page_load_time=10.0,
            wait_between_actions=2.0,
        )
        
        self.browser_context = await self.browser.new_context(config=context_config)
        if not self.controller:
            self.controller = CustomController()
        
        # 加载cookies（如果启用cookie登录）
        if self.use_cookie_login:
            await self._load_cookies()
        
        logger.info("浏览器设置完成（使用优化配置）")

    def _scan_available_posts(self) -> List[Dict[str, Any]]:
        """动态扫描可用的发布内容"""
        posts = []
        
        # 只扫描专门的小红书发帖目录
        scan_dir = self.posts_dir
        
        logger.info("🔍 扫描小红书发布内容...")
        
        if not scan_dir.exists():
            logger.info(f"📁 创建目录: {scan_dir}")
            scan_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("⚠️ 发帖目录为空，请在此目录下放置内容")
            return posts
            
        logger.info(f"📂 扫描目录: {scan_dir}")
        
        # 扫描子目录作为发布内容
        for item in scan_dir.iterdir():
            if item.is_dir():
                post_data = self._scan_post_directory(item)
                if post_data:
                    posts.append(post_data)
                    title = post_data.get('title', 'untitled')
                    images = len(post_data.get('images', []))
                    text_len = len(post_data.get('text_content', ''))
                    logger.info(f"  ✅ 找到内容: {title} ({images}张图片, {text_len}字)")
        
        if posts:
            logger.info(f"📊 扫描完成，共找到 {len(posts)} 个发布内容")
        else:
            logger.warning("⚠️ 未找到发布内容")
            logger.info("💡 请在以下目录创建子目录并放置内容：")
            logger.info(f"   {scan_dir}")
            logger.info("   每个子目录代表一个发布内容，包含图片和文案文件")
        
        return posts
    
    def _scan_post_directory(self, dir_path: Path) -> Optional[Dict[str, Any]]:
        """扫描单个目录的发布内容"""
        try:
            post_data = {
                "title": dir_path.name,
                "text_content": "",
                "images": [],
                "source_dir": str(dir_path),
                "scanned_at": datetime.now().isoformat()
            }
            
            # 支持的图片格式
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.tif'}
            text_extensions = {'.txt', '.md'}
            
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    file_ext = file_path.suffix.lower()
                    
                    # 处理图片文件
                    if file_ext in image_extensions:
                        file_size = file_path.stat().st_size / (1024 * 1024)  # MB
                        post_data["images"].append({
                            "path": str(file_path),
                            "name": file_path.name,
                            "size_mb": round(file_size, 2)
                        })
                    
                    # 处理文本文件
                    elif file_ext in text_extensions:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if content:
                                    post_data["text_content"] += content + "\n\n"
                        except Exception as e:
                            logger.warning(f"读取文本文件失败 {file_path}: {e}")
            
            # 清理文本内容
            post_data["text_content"] = post_data["text_content"].strip()
            
            # 🔧 简化：每个帖子只保留第一张图片，避免多图上传的复杂问题
            if post_data["images"]:
                first_image = post_data["images"][0]
                post_data["images"] = [first_image]
                logger.info(f"📸 帖子 '{post_data['title']}' 使用第一张图片: {first_image['name']}")
            
            # 只有包含图片或文本的目录才被认为是有效的发布内容
            if post_data["images"] or post_data["text_content"]:
                return post_data
            
            return None
            
        except Exception as e:
            logger.error(f"扫描目录失败 {dir_path}: {e}")
            return None
    
    def _register_signal_handlers(self):
        """注册信号处理器，模仿browser_use_agent的信号处理"""
        def signal_handler(signum, frame):
            logger.info(f"🛑 收到信号 {signum}，正在优雅关闭...")
            self.stop_requested = True
            
        try:
            signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
            signal.signal(signal.SIGTERM, signal_handler)  # Terminate
            logger.info("✅ 信号处理器注册成功")
        except Exception as e:
            logger.warning(f"⚠️ 信号处理器注册失败: {e}")
    
    async def _delete_post_directory_async(self, post_data: Dict[str, Any]) -> bool:
        """
        异步删除已发布成功的帖子目录,防止重复发布
        
        Args:
            post_data: 包含source_dir信息的帖子数据
            
        Returns:
            bool: 删除成功返回True，失败返回False
        """
        source_dir = post_data.get("source_dir")
        if not source_dir:
            logger.warning("⚠️ 帖子数据中缺少source_dir信息，无法删除")
            return False
        
        source_path = Path(source_dir)
        if not source_path.exists():
            logger.warning(f"⚠️ 帖子目录不存在: {source_path}")
            return False
        
        try:
            # 检查是否为有效的帖子目录（在posts_dir下）
            if not source_path.is_relative_to(self.posts_dir):
                logger.error(f"❌ 安全检查失败：目录不在发帖目录范围内: {source_path}")
                return False
            
            # 异步删除整个目录
            def _delete_sync():
                shutil.rmtree(source_path)
                return True
            
            # 使用 asyncio.to_thread 将同步删除操作包装成异步
            await asyncio.to_thread(_delete_sync)
            logger.info(f"🗑️ 已异步删除成功发布的帖子目录: {source_path}")
            
            # 从available_posts中移除该帖子
            self.available_posts = [
                post for post in self.available_posts 
                if post.get("source_dir") != source_dir
            ]
            logger.info(f"📊 已更新可用帖子列表，剩余 {len(self.available_posts)} 个")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 异步删除帖子目录失败 {source_path}: {e}")
            return False
    
    def _schedule_delete_post_directory(self, post_data: Dict[str, Any]) -> None:
        """
        调度异步删除帖子目录任务（不阻塞主流程）
        
        Args:
            post_data: 包含source_dir信息的帖子数据
        """
        async def _delete_task():
            try:
                success = await self._delete_post_directory_async(post_data)
                if success:
                    logger.info(f"🗑️ 后台删除成功: {post_data.get('title', '未知')}")
                else:
                    logger.warning(f"⚠️ 后台删除失败: {post_data.get('title', '未知')}")
            except Exception as e:
                logger.error(f"❌ 后台删除任务异常: {e}")
        
        # 创建后台任务，不等待完成
        asyncio.create_task(_delete_task())
    
    async def _load_cookies(self) -> bool:
        """加载cookies到浏览器"""
        try:
            cookies = []
            
            # 优先使用指定的cookie文件
            if self.cookie_file_path and os.path.exists(self.cookie_file_path):
                logger.info(f"从指定路径加载cookies: {self.cookie_file_path}")
                cookies = self.cookie_manager.load_cookies_from_file(self.cookie_file_path)
            else:
                # 尝试加载已保存的cookies
                cookies = self.cookie_manager.load_saved_cookies()
                
                # 如果没有已保存的cookies，尝试从默认位置加载
                if not cookies:
                    default_paths = [
                        "./tmp/cookies/xiaohongshu_cookies.json",
                        "./cookies/xiaohongshu.json",
                        "./xiaohongshu_cookies.json"
                    ]
                    
                    for path in default_paths:
                        if os.path.exists(path):
                            logger.info(f"从默认路径加载cookies: {path}")
                            cookies = self.cookie_manager.load_cookies_from_file(path)
                            if cookies:
                                break
            
            if cookies:
                # 设置cookies到浏览器
                success = await self.cookie_manager.set_browser_cookies(self.browser_context, cookies)
                if success:
                    logger.info(f"✅ 成功加载 {len(cookies)} 个cookies")
                    return True
                else:
                    logger.warning("❌ 设置cookies到浏览器失败")
            else:
                logger.info("📁 未找到可用的cookies文件")
                
            return False
            
        except Exception as e:
            logger.error(f"加载cookies时出错: {e}")
            return False
    
    async def _verify_cookie_login(self) -> bool:
        """验证cookie登录状态"""
        try:
            logger.info("验证cookie登录状态...")
            
            # 先尝试加载cookies
            cookie_success = await self._load_cookies()
            if not cookie_success:
                logger.warning("❌ 无法加载cookies")
                return False
            
            # 通过访问需要登录的页面来验证cookies是否有效
            logger.info("🔍 验证cookies是否有效...")
            
            # 访问创作者页面验证登录状态
            if not self.browser_context:
                logger.error("浏览器上下文未初始化")
                return False
                
            page = await self.browser_context.get_current_page()
            if not page:
                await self.browser_context.navigate_to("https://creator.xiaohongshu.com")
                page = await self.browser_context.get_current_page()
            else:
                await page.goto("https://creator.xiaohongshu.com")
                
            # 等待页面加载
            await asyncio.sleep(3)
            
            # 检查当前URL
            current_url = page.url
            logger.info(f"📍 当前URL: {current_url}")
            
            if "creator.xiaohongshu.com" in current_url:
                logger.info("✅ 成功访问创作者页面 - Cookie登录有效")
                return True
            elif "login" in current_url.lower() or "signin" in current_url.lower():
                logger.warning("❌ 被重定向到登录页 - Cookie登录失败")
                return False
            else:
                logger.warning("⚠️ 重定向到其他页面，状态不明")
                return False
                
        except Exception as e:
            logger.error(f"验证cookie登录状态时出错: {e}")
            return False
    
    async def close_browser(self) -> None:
        """关闭浏览器"""
        if self.browser_context:
            try:
                await self.browser_context.close()
                self.browser_context = None
                logger.info("浏览器上下文已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器上下文时出错: {e}")
        
        if self.browser:
            try:
                await self.browser.close()
                self.browser = None
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}")
    
    def create_post_content(self, post_data: Dict[str, Any]) -> str:
        """创建发帖内容"""
        content = post_data.get("text_content", "").strip()
        
        # 如果没有文案，根据图片生成简单的内容
        if not content and post_data.get("images"):
            content = "分享一些精彩内容 📸"
        
        # 如果还是没有内容，使用默认内容
        if not content:
            content = "今天的分享 ✨"
        
        return content

    async def login_xiaohongshu(self, status_callback=None) -> bool:
        """只使用cookie登录小红书"""
        try:
            # 检查停止状态
            if self.stop_requested:
                logger.info("🛑 任务已停止，跳过登录")
                return False

            await self.setup_browser()

            # setup_browser后再次检查停止状态
            if self.stop_requested:
                logger.info("🛑 任务已停止，跳过登录")
                return False

            # 只使用cookie登录
            if not self.use_cookie_login:
                error_msg = "未启用Cookie登录。请在【Browser Settings】中启用并提供有效的Cookie文件。"
                logger.error(f"❌ {error_msg}")
                if status_callback:
                    await status_callback(f"❌ {error_msg}")
                return False

            logger.info("🍪 尝试使用cookie登录...")
            if status_callback:
                await status_callback("🍪 尝试使用Cookie登录...")

            cookie_success = await self._verify_cookie_login()

            if cookie_success:
                logger.info("✅ Cookie登录成功")
                if status_callback:
                    await status_callback("✅ Cookie登录成功")
                return True
            else:
                error_msg = "Cookie登录失败，Cookie可能已过期或无效。请在【Browser Settings】中更新Cookie文件。"
                logger.warning(f"⚠️ {error_msg}")
                if status_callback:
                    await status_callback(f"❌ {error_msg}")
                return False

        except Exception as e:
            error_msg = f"登录小红书时出错: {e}"
            logger.error(error_msg, exc_info=True)
            if status_callback:
                await status_callback(f"❌ {error_msg}")
            return False

    async def verify_login_status(self) -> bool:
        """验证小红书登录状态"""
        try:
            # 🔧 关键修复：检查停止状态
            if self.stop_requested:
                logger.info("🛑 任务已停止，跳过验证登录状态")
                return False
            verify_task = """
            请检查当前是否已登录小红书：
            1. 查看页面右上角是否有用户头像或用户名
            2. 尝试访问"我的"或"个人中心"页面
            3. 查看是否能看到"发布"或"创作"按钮
            4. 如果看到"登录"按钮，说明未登录
            5. 如果看到用户相关信息，说明已登录
            
            请明确返回"已登录"或"未登录"状态。
            """
            
            # 创建局部变量避免类型问题
            controller = self.controller
            assert controller is not None, "Controller不能为None"
                
            browser_agent = Agent(
                task=verify_task,
                llm=self.llm,
                browser=self.browser,
                browser_context=self.browser_context,
                controller=controller,
            )
            
            try:
                result = await browser_agent.run(max_steps=5)
            except (asyncio.CancelledError, Exception) as e:
                # 处理任务被取消或浏览器被关闭的情况
                if self.stop_requested:
                    logger.info("🛑 验证登录状态被停止请求中断")
                    return False
                elif "browser" in str(e).lower() or "context" in str(e).lower() or "connection" in str(e).lower():
                    logger.info("🛑 验证登录状态因浏览器关闭而中断")
                    return False
                else:
                    logger.warning(f"验证登录状态出现异常: {e}")
                    return False
            
            final_result = str(result.final_result()).lower()
            
            if "已登录" in final_result or "logged in" in final_result:
                logger.info("验证确认：已登录小红书")
                return True
            else:
                logger.warning("验证确认：未登录小红书")
                return False
                
        except Exception as e:
            logger.error(f"验证登录状态时出错: {e}")
            return False
    
    async def post_to_xiaohongshu(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """发布到小红书"""
        try:
            # 🔧 关键修复：检查停止状态
            if self.stop_requested:
                logger.info("🛑 任务已停止，跳过发布")
                return {
                    "success": False,
                    "error": "任务被用户停止",
                    "post_title": post_data.get("title", "未知"),
                    "message": "发布过程被用户停止",
                    "analysis": {"decision_reason": "用户停止任务"}
                }
            # 准备发帖内容
            content = self.create_post_content(post_data)
            images = post_data.get("images", [])
            
            logger.info(f"准备发布小红书帖子: {post_data['title']}")
            logger.info(f"内容长度: {len(content)}, 图片数量: {len(images)} (已简化为单图)")
            
            # 🔧 修复：提取图片路径字符串
            if images:
                # 如果images是字典列表，提取path字段
                if images and isinstance(images[0], dict):
                    image_paths = [img.get("path", str(img)) for img in images]
                else:
                    # 如果images已经是字符串列表，直接使用
                    image_paths = images
                
                logger.info(f"图片路径: {image_paths}")
                
                # 有图片的发布流程
                post_task = f"""
                ### 角色
                你是一个精通小红书平台的社交媒体运营专家。

                ### 任务目标
                发布一篇包含 **图片** 的图文笔记。

                ### 核心物料
                - **图片文件**: {image_paths[0] if image_paths else '无'}
                - **帖子内容 (标题和正文)**:  {content}
                
                操作步骤:
                1. 前往小红书创作中心页面: `https://creator.xiaohongshu.com/publish/publish`
                2. 登录（如果需要）
                3. **选择发布模式**:
                    - 在页面上找到并点击“发布图文”或类似按钮，确保你进入的是图文发布流程，而不是视频发布。
                    - **验证**: 页面上必须出现“拖拽或点击上传图片”的区域。
                4. **图片上传**（关键步骤）：
                   图片文件: {image_paths[0] if image_paths else '无'}
                   
                   **上传步骤**：
                   - 找到文件输入元素
                   - 使用upload_file动作上传图片
                   - **重要：必须等待并确认上传真正完成**
                6. **上传验证**：
                   - 检查是否出现图片预览/缩略图
                   - 确认页面已离开上传界面
                   - 验证是否出现标题和描述输入框
                   - 如果仍在上传界面，说明上传失败，需要重试
                7. 填写标题
                8. 填写正文内容（包含所有标签）
                9. **重要：不要点击"话题"或"添加话题"按钮**
                10. 直接点击"发布"按钮完成发布


                成功标准：
                - 首先成功选择图文上传模式
                - 使用upload_file动作成功上传1张图片
                - **必须确认页面显示图片预览且进入编辑界面**
                - 标题和正文完整填写
                - 成功点击发布按钮
                - 看到发布成功提示或URL包含"published=true"参数

                **关键问题处理指南**：
                - **如果遇到"你访问的页面不见了"错误**：立即刷新页面或重新访问小红书创作平台
                - **如果页面空白或加载失败**：等待5秒后刷新页面，或者重新导航到创作平台
                - **如果在视频上传界面**：立即返回或重新选择图文上传
                - **如果upload_file报告成功但页面仍显示"拖拽图片到此"**：说明上传实际失败，必须重新上传
                - **如果找不到标题和描述输入框**：检查图片是否真正上传成功，可能需要重新上传
                - **页面卡在上传界面**：确认图片是否上传成功，重新选择文件或刷新页面重试
                - **找不到发布按钮**：检查URL是否包含"published=true"，可能已发布成功
                - **出现弹窗或错误**：尝试关闭弹窗或按ESC键，然后继续
                - **网络连接问题**：等待几秒后重试，或者刷新页面重新开始
                """
            else:
                # 小红书不支持无图片发布，直接返回错误
                logger.error("❌ 小红书不支持发布纯文字帖子，必须包含图片")
                return {
                    "success": False,
                    "error": "小红书不支持发布纯文字帖子",
                    "post_title": post_data.get("title", "未知"),
                    "message": "小红书是图片分享平台，所有帖子都必须包含至少一张图片。请在帖子目录中添加图片文件。",
                    "analysis": {
                        "decision_reason": "小红书平台限制：不支持纯文字发布"
                    }
                }
            
            if not self.controller:
                self.controller = CustomController()
                
            # 创建局部变量避免类型问题
            controller = self.controller
            assert controller is not None, "Controller不能为None"
            
            # 🔧 修复：准备可用文件路径列表
            available_file_paths = []
            if images:
                if images and isinstance(images[0], dict):
                    # 如果是字典格式，提取path字段
                    available_file_paths = [img.get("path", "") for img in images]
                else:
                    # 如果是字符串格式，直接使用
                    available_file_paths = list(images)
            
            logger.info(f"可用文件路径: {available_file_paths}")
                
            browser_agent = Agent(
                task=post_task,
                llm=self.llm,
                browser=self.browser,
                browser_context=self.browser_context,
                controller=controller,
                available_file_paths=available_file_paths,  # 🔧 关键修复：提供文件路径
            )
            
            try:
                result = await browser_agent.run(max_steps=20)
            except (asyncio.CancelledError, Exception) as e:
                # 处理任务被取消或浏览器被关闭的情况
                if self.stop_requested:
                    logger.info("🛑 发布过程被停止请求中断")
                    return {
                        "success": False,
                        "error": "任务被用户停止",
                        "post_title": post_data.get("title", "未知"),
                        "message": "发布过程被用户停止",
                        "analysis": {"decision_reason": "用户停止任务"}
                    }
                elif "browser" in str(e).lower() or "context" in str(e).lower() or "connection" in str(e).lower():
                    logger.info("🛑 发布过程因浏览器关闭而中断")
                    return {
                        "success": False,
                        "error": "浏览器连接中断",
                        "post_title": post_data.get("title", "未知"),
                        "message": "发布过程因浏览器关闭而中断",
                        "analysis": {"decision_reason": "浏览器连接中断"}
                    }
                else:
                    logger.warning(f"发布过程出现异常: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "post_title": post_data.get("title", "未知"),
                        "message": "发布过程出现异常",
                        "analysis": {"decision_reason": "发布异常"}
                    }
            
            final_result = result.final_result()
            final_result_str = str(final_result).lower()
            
            # 🔧 修复: 基于Browser Agent的实际执行结果判断成功/失败
            success_indicators = [
                "发布成功", "已发布", "publish success", "successfully published",
                "发表成功", "posting completed", "发送成功", "published=true"
            ]
            
            failure_indicators = [
                "failed", "error", "错误", "失败", "未完成", "incomplete",
                "failed to complete", "maximum steps", "无法", "不能"
            ]
            
            # 🔧 新增：检查需要重试的错误
            retry_indicators = [
                "你访问的页面不见了", "页面不见了", "page not found", "404", 
                "网络错误", "network error", "连接失败", "connection failed",
                "页面加载失败", "page load failed", "空白页面", "blank page"
            ]
            
            # 检查成功指标（包括URL和结果中的成功信息）
            is_success = any(indicator in final_result_str for indicator in success_indicators)
            
            # 🔧 新增：检查整个执行结果字符串中是否包含成功URL
            full_result_str = str(result).lower()
            url_success = "published=true" in full_result_str
            
            # 检查失败指标
            has_failure = any(indicator in final_result_str for indicator in failure_indicators)
            
            # 🔧 新增：检查是否需要重试
            needs_retry = any(indicator in final_result_str for indicator in retry_indicators)
            
            # 🔧 综合判断：结合明确的成功/失败指标、URL检查和重试判断
            if needs_retry and not (is_success or url_success):
                # 需要重试的情况，返回特殊的错误类型
                logger.warning(f"⚠️ 检测到需要重试的错误: {final_result_str}")
                return {
                    "success": False,
                    "error": "页面错误，需要重试",
                    "post_title": post_data["title"],
                    "content": content,
                    "images_count": len(images),
                    "result": str(final_result),
                    "retry_needed": True,  # 标记需要重试
                    "analysis": {
                        "final_result": final_result_str,
                        "has_success_indicators": is_success,
                        "has_failure_indicators": has_failure,
                        "url_success": url_success,
                        "needs_retry": needs_retry,
                        "decision_reason": "检测到页面错误，建议重试"
                    }
                }
            elif has_failure and not (is_success or url_success):
                actual_success = False
                logger.warning(f"❌ 发布失败，检测到失败指标: {final_result_str}")
            elif is_success or url_success:
                actual_success = True
                success_reason = "Agent执行结果包含成功指标" if is_success else "URL包含published=true参数"
                logger.info(f"✅ 发布成功，{success_reason}: {final_result_str}")
                
                # 🔧 新增：发布成功后异步删除帖子目录，防止重复发布（不阻塞主流程）
                self._schedule_delete_post_directory(post_data)
                logger.info(f"🗑️ 已调度删除任务: {post_data['title']}")
            else:
                # 如果没有明确指标，基于任务是否正常完成来判断
                # 检查是否因为达到最大步数而终止
                if "maximum steps" in final_result_str or len(final_result_str) < 10:
                    actual_success = False
                    logger.warning(f"⚠️ 发布状态不明确，但可能失败: {final_result_str}")
                else:
                    actual_success = True
                    logger.info(f"✅ 发布完成: {final_result_str}")
                    
                    # 🔧 新增：发布成功后异步删除帖子目录，防止重复发布（不阻塞主流程）
                    self._schedule_delete_post_directory(post_data)
                    logger.info(f"🗑️ 已调度删除任务: {post_data['title']}")
            
            return {
                "success": actual_success,  # 🔧 修复: 使用实际的成功判断
                "post_title": post_data["title"],
                "content": content,
                "images_count": len(images),
                "result": str(final_result),
                "analysis": {
                    "final_result": final_result_str,
                    "has_success_indicators": is_success,
                    "has_failure_indicators": has_failure,
                    "url_success": url_success,
                    "needs_retry": needs_retry,
                    "decision_reason": "基于Agent执行结果和URL状态的智能判断"
                }
            }
            
        except Exception as e:
            logger.error(f"发布小红书帖子时出错: {e}")
            return {
                "success": False,
                "error": str(e),
                "post_title": post_data.get("title", "未知"),
                "analysis": {
                    "decision_reason": "发生异常错误"
                }
            }
    
    @time_execution_async("--run (xiaohongshu_agent)")
    async def run_posting_task(self, max_posts: int = 5, status_callback=None) -> List[Dict[str, Any]]:
        """
        运行小红书发帖任务
        
        Args:
            max_posts: 最大发布帖子数量
            status_callback: 可选的回调函数，用于更新任务状态
        """
        
        # 🔧 新增：确保开始时状态是干净的
        logger.info("🔄 初始化发帖任务，检查状态...")
        
        # 如果之前有未完成的任务，先清理
        if self.is_running or self.stop_requested:
            logger.warning("⚠️ 检测到之前任务状态未清理，正在重置...")
            await self.close_browser()
            self.is_running = False
            self.is_paused = False
            self.stop_requested = False
            self.browser = None
            self.browser_context = None
            self.controller = None
            logger.info("✅ 状态已重置")
        
        self.current_task_id = str(uuid.uuid4())
        results = []
        self.is_running = True
        
        async def update_status(message: str, details: Dict[str, Any] = None):
            """更新状态的辅助函数"""
            if status_callback:
                await status_callback(message, details or {})
        
        try:
            logger.info("🚀 开始小红书发帖任务...")
            await update_status("🚀 开始小红书发帖任务...")
            
            # 检查停止信号
            if self.stop_requested:
                logger.info("🛑 接收到停止信号，任务终止")
                return results
            
            # 使用动态扫描的内容或重新扫描
            await update_status("📂 扫描发帖内容...")
            posts = self.available_posts or self._scan_available_posts()
            
            if not posts:
                logger.warning("⚠️ 未找到发帖内容")
                await update_status("❌ 未找到发帖内容", {
                    "message": "请在tmp目录下放置文案文件(.txt/.md)和图片文件"
                })
                return [{
                    "success": False,
                    "error": "没有找到可发布的内容",
                    "message": "请在tmp目录下放置文案文件(.txt/.md)和图片文件",
                    "timestamp": datetime.now().isoformat()
                }]
            
            # 登录小红书
            logger.info("🔐 尝试登录小红书...")
            await update_status("🔐 正在登录小红书...")
            
            # 检查取消状态
            await asyncio.sleep(0)
            
            login_success = await self.login_xiaohongshu(status_callback=update_status)
            if not login_success:
                logger.error("❌ 登录失败")
                await update_status("❌ 小红书登录失败", {
                    "message": "请检查网络连接和登录信息"
                })
                return [{
                    "success": False,
                    "error": "小红书登录失败",
                    "message": "请检查网络连接和登录信息",
                    "timestamp": datetime.now().isoformat()
                }]
            
            # 检查取消状态
            await asyncio.sleep(0)
            
            logger.info("✅ 登录成功")
            await update_status("✅ 登录成功，准备发布帖子...")
            
            # 发布帖子
            posts_to_publish = posts[:max_posts]
            logger.info(f"📝 准备发布 {len(posts_to_publish)} 条内容")
            await update_status(f"📝 准备发布 {len(posts_to_publish)} 条内容", {
                "total_posts": len(posts_to_publish),
                "current_post": 0
            })
            
            consecutive_failures = 0
            max_failures = 3
            post_count = 0
            
            for i, post_data in enumerate(posts_to_publish, 1):
                # 检查控制信号
                if self.stop_requested:
                    logger.info(f"🛑 接收到停止信号，已完成 {post_count}/{len(posts_to_publish)} 条内容")
                    break
                
                # 检查当前任务是否被取消
                current_task = asyncio.current_task()
                if current_task and current_task.cancelled():
                    logger.info(f"🛑 任务被取消，已完成 {post_count}/{len(posts_to_publish)} 条内容")
                    raise asyncio.CancelledError()
                
                while self.is_paused:
                    logger.info("⏸️ 任务已暂停，等待恢复...")
                    await asyncio.sleep(1)
                    if self.stop_requested:
                        break
                    # 检查任务是否被取消
                    if current_task and current_task.cancelled():
                        logger.info("🛑 任务在暂停期间被取消")
                        raise asyncio.CancelledError()
                
                if self.stop_requested:
                    break
                
                # 检查连续失败次数
                if consecutive_failures >= max_failures:
                    logger.error(f"❌ 连续失败 {max_failures} 次，停止任务")
                    await update_status(f"❌ 连续失败 {max_failures} 次，停止任务", {
                        "current_post": i,
                        "total_posts": len(posts_to_publish),
                        "failed_count": consecutive_failures
                    })
                    break
                
                title = post_data.get('title', 'untitled')
                logger.info(f"📤 发布第 {i}/{len(posts_to_publish)} 篇帖子: {title}")
                
                # 实时更新当前发布状态
                await update_status(f"📤 正在发布第 {i}/{len(posts_to_publish)} 篇帖子", {
                    "current_post": i,
                    "total_posts": len(posts_to_publish),
                    "post_title": title,
                    "post_content_length": len(post_data.get('text_content', '')),
                    "post_images_count": len(post_data.get('images', [])),
                    "status": "准备发布"
                })
                
                # 检查取消状态
                await asyncio.sleep(0)
                
                try:
                    # 发布开始
                    await update_status(f"📤 正在发布: {title}", {
                        "current_post": i,
                        "total_posts": len(posts_to_publish),
                        "post_title": title,
                        "status": "发布中"
                    })
                    
                    # 🔧 新增：添加重试机制
                    max_retries = 2
                    retry_count = 0
                    result = None
                    
                    while retry_count <= max_retries:
                        if self.stop_requested:
                            break
                            
                        if retry_count > 0:
                            logger.info(f"🔄 第 {retry_count} 次重试发布: {title}")
                            await update_status(f"🔄 第 {retry_count} 次重试发布: {title}", {
                                "current_post": i,
                                "total_posts": len(posts_to_publish),
                                "post_title": title,
                                "status": f"第{retry_count}次重试",
                                "retry_count": retry_count
                            })
                            
                            # 重试前等待一段时间
                            await asyncio.sleep(5)
                        
                        result = await self.post_to_xiaohongshu(post_data)
                        
                        # 检查是否需要重试
                        if result.get("retry_needed", False) and retry_count < max_retries:
                            retry_count += 1
                            logger.warning(f"⚠️ 发布遇到可重试错误，准备第 {retry_count} 次重试: {result.get('error', '')}")
                            continue
                        else:
                            # 不需要重试或已达到最大重试次数
                            break
                    
                    result.update({
                        "step_number": i,
                        "total_steps": len(posts_to_publish),
                        "timestamp": datetime.now().isoformat(),
                        "retry_count": retry_count
                    })
                    results.append(result)
                    
                    if result["success"]:
                        post_count += 1
                        consecutive_failures = 0  # 重置失败计数
                        retry_msg = f" (经过 {retry_count} 次重试)" if retry_count > 0 else ""
                        logger.info(f"✅ 第 {i} 篇帖子发布成功: {title}{retry_msg}")
                        
                        # 实时更新成功状态
                        await update_status(f"✅ 第 {i} 篇帖子发布成功: {title}{retry_msg}", {
                            "current_post": i,
                            "total_posts": len(posts_to_publish),
                            "post_title": title,
                            "status": "发布成功",
                            "success_count": post_count,
                            "failed_count": len(results) - post_count,
                            "retry_count": retry_count
                        })
                        
                        # 直接继续下一篇，不等待
                        if i < len(posts_to_publish) and not self.stop_requested:
                            logger.info("🚀 继续发布下一篇帖子...")
                    else:
                        consecutive_failures += 1
                        retry_msg = f" (已重试 {retry_count} 次)" if retry_count > 0 else ""
                        logger.error(f"❌ 第 {i} 篇帖子发布失败: {title}{retry_msg}")
                        
                        # 实时更新失败状态
                        error_msg = result.get('error', '未知错误')
                        await update_status(f"❌ 第 {i} 篇帖子发布失败: {title}{retry_msg}", {
                            "current_post": i,
                            "total_posts": len(posts_to_publish),
                            "post_title": title,
                            "status": "发布失败",
                            "error": error_msg,
                            "success_count": post_count,
                            "failed_count": len(results) - post_count,
                            "retry_count": retry_count
                        })
                        
                        # 失败后等待更长时间
                        if i < len(posts_to_publish) and not self.stop_requested:
                            wait_time = 5 + (consecutive_failures * 3)
                            logger.info(f"⏱️ 发布失败，等待 {wait_time} 秒后重试...")
                            
                            for wait_sec in range(wait_time):
                                if self.stop_requested:
                                    break
                                # 检查任务是否被取消
                                current_task = asyncio.current_task()
                                if current_task and current_task.cancelled():
                                    logger.info("🛑 任务在等待期间被取消")
                                    raise asyncio.CancelledError()
                                
                                # 实时更新等待状态
                                await update_status(f"⏱️ 发布失败，等待 {wait_time - wait_sec} 秒后重试", {
                                    "current_post": i,
                                    "total_posts": len(posts_to_publish),
                                    "post_title": title,
                                    "status": "等待重试",
                                    "wait_time": wait_time - wait_sec
                                })
                                
                                await asyncio.sleep(1)
                
                except Exception as e:
                    consecutive_failures += 1
                    error_result = {
                        "success": False,
                        "error": str(e),
                        "post_title": title,
                        "step_number": i,
                        "total_steps": len(posts_to_publish),
                        "timestamp": datetime.now().isoformat()
                    }
                    results.append(error_result)
                    logger.error(f"💥 第 {i} 篇帖子发布异常: {e}")
                    
                    # 实时更新异常状态
                    await update_status(f"💥 第 {i} 篇帖子发布异常: {title}", {
                        "current_post": i,
                        "total_posts": len(posts_to_publish),
                        "post_title": title,
                        "status": "发布异常",
                        "error": str(e),
                        "success_count": post_count,
                        "failed_count": len(results) - post_count
                    })
            
            # 任务完成统计
            successful_posts = sum(1 for r in results if r.get('success'))
            total_attempts = len(results)
            
            if self.stop_requested:
                logger.info(f"🛑 任务被中断，已完成 {successful_posts}/{total_attempts} 条内容")
                await update_status(f"🛑 任务被中断", {
                    "success_count": successful_posts,
                    "total_attempts": total_attempts,
                    "status": "任务中断"
                })
            else:
                logger.info(f"🎉 发帖任务完成！成功发布 {successful_posts}/{total_attempts} 条内容")
                await update_status(f"🎉 发帖任务完成！", {
                    "success_count": successful_posts,
                    "total_attempts": total_attempts,
                    "status": "任务完成"
                })
    
        except KeyboardInterrupt:
            logger.info("⌨️ 接收到键盘中断，优雅停止任务")
            return results
        except Exception as e:
            logger.error(f"💥 运行发帖任务时出错: {e}")
            results.append({
                "success": False,
                "error": str(e),
                "message": "发帖任务执行失败",
                "timestamp": datetime.now().isoformat(),
                "fatal": True
            })
        finally:
            self.is_running = False
            await self.close_browser()
            logger.info("🏁 任务执行完成")
        
        return results
    

    def pause(self):
        """暂停任务"""
        self.is_paused = True
        logger.info("⏸️ 任务已暂停")
    
    def resume(self):
        """恢复任务"""
        self.is_paused = False
        logger.info("▶️ 任务已恢复")
    
    def request_stop(self):
        """请求停止任务"""
        self.stop_requested = True
        logger.info("🛑 已请求停止任务")
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "stop_requested": self.stop_requested,
            "current_task_id": self.current_task_id,
            "available_posts_count": len(self.available_posts),
            "browser_ready": self.browser is not None,
            "cookie_login_enabled": self.use_cookie_login
        }
    
    async def stop(self):
        """停止当前任务"""
        logger.info("🛑 停止小红书发帖任务")
        self.request_stop()
        await self.close_browser()
        self.current_task_id = None
        
        # 🔧 关键修复：重置所有状态标志，确保下次可以重新开始
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False  # 重置停止请求状态
        
        # 🔧 新增：彻底清理所有组件状态
        self.browser = None
        self.browser_context = None
        self.controller = None  # 重置控制器
        
        # 🔧 新增：重新扫描可用内容，确保内容列表是最新的
        self.available_posts = self._scan_available_posts()
        
        logger.info("🔄 已完全重置Agent状态，所有组件已清理，可以重新开始任务") 