import pdb

import pyperclip
from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller, DoneAction
from browser_use.controller.registry.service import Registry, RegisteredAction
from main_content_extractor import MainContentExtractor
from browser_use.controller.views import (
    ClickElementAction,
    DoneAction,
    ExtractPageContentAction,
    GoToUrlAction,
    InputTextAction,
    OpenTabAction,
    ScrollAction,
    SearchGoogleAction,
    SendKeysAction,
    SwitchTabAction,
)
import logging
import inspect
import asyncio
import os
from langchain_core.language_models.chat_models import BaseChatModel
from browser_use.agent.views import ActionModel, ActionResult

from src.utils.mcp_client import create_tool_param_model, setup_mcp_client_and_tools

from browser_use.utils import time_execution_sync

logger = logging.getLogger(__name__)

Context = TypeVar('Context')


class CustomController(Controller):
    def __init__(self, exclude_actions: list[str] = [],
                 output_model: Optional[Type[BaseModel]] = None,
                 ask_assistant_callback: Optional[Union[Callable[[str, BrowserContext], Dict[str, Any]], Callable[
                     [str, BrowserContext], Awaitable[Dict[str, Any]]]]] = None,
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model)
        self._register_custom_actions()
        self.ask_assistant_callback = ask_assistant_callback
        self.mcp_client = None
        self.mcp_server_config = None

    def _register_custom_actions(self):
        """Register all custom browser actions"""

        @self.registry.action(
            "When executing tasks, prioritize autonomous completion. However, if you encounter a definitive blocker "
            "that prevents you from proceeding independently – such as needing credentials you don't possess, "
            "requiring subjective human judgment, needing a physical action performed, encountering complex CAPTCHAs, "
            "or facing limitations in your capabilities – you must request human assistance."
        )
        async def ask_for_assistant(query: str, browser: BrowserContext):
            if self.ask_assistant_callback:
                if inspect.iscoroutinefunction(self.ask_assistant_callback):
                    user_response = await self.ask_assistant_callback(query, browser)
                else:
                    user_response = self.ask_assistant_callback(query, browser)
                msg = f"AI ask: {query}. User response: {user_response['response']}"
                logger.info(msg)
                return ActionResult(extracted_content=msg, include_in_memory=True)
            else:
                return ActionResult(extracted_content="Human cannot help you. Please try another way.",
                                    include_in_memory=True)

        @self.registry.action(
            'Upload file to interactive element with file path and verify upload completion',
        )
        async def upload_file(index: int, path: str, browser: BrowserContext, available_file_paths: list[str]):
            if path not in available_file_paths:
                return ActionResult(error=f'File path {path} is not available')

            if not os.path.exists(path):
                return ActionResult(error=f'File {path} does not exist')

            # 获取上传前的页面状态
            try:
                page = await browser.get_current_page()
                initial_page_content = await page.content()
                
                # 检查是否在正确的页面（小红书图文上传页面）
                if "小红书" in initial_page_content or "xiaohongshu" in initial_page_content.lower():
                    # 检查是否在视频上传界面
                    if "视频" in initial_page_content and "图文" not in initial_page_content:
                        return ActionResult(error='当前在视频上传界面，请先选择图文上传模式')
                    
                    # 检查是否在正确的图文上传界面
                    if "拖拽图片到此" not in initial_page_content and "点击上传" not in initial_page_content and "上传图片" not in initial_page_content:
                        return ActionResult(error='当前不在图文上传界面，请先选择图文上传模式')
                
            except Exception as e:
                logger.warning(f"无法获取初始页面内容: {e}")
                initial_page_content = ""

            dom_el = await browser.get_dom_element_by_index(index)

            file_upload_dom_el = dom_el.get_file_upload_element()

            if file_upload_dom_el is None:
                msg = f'No file upload element found at index {index}'
                logger.info(msg)
                return ActionResult(error=msg)

            file_upload_el = await browser.get_locate_element(file_upload_dom_el)

            if file_upload_el is None:
                msg = f'No file upload element found at index {index}'
                logger.info(msg)
                return ActionResult(error=msg)

            try:
                # 第1步：设置文件
                await file_upload_el.set_input_files(path)
                logger.info(f"文件已设置到input元素: {path}")
                
                # 第2步：等待一段时间让上传开始
                await asyncio.sleep(2)
                
                # 第3步：检查页面是否发生变化（最多等待10秒）
                upload_success = False
                max_wait_time = 10
                check_interval = 1
                waited_time = 0
                
                while waited_time < max_wait_time and not upload_success:
                    await asyncio.sleep(check_interval)
                    waited_time += check_interval
                    
                    try:
                        page = await browser.get_current_page()
                        current_page_content = await page.content()
                        
                        # 检查页面变化的多个指标
                        success_indicators = [
                            "上传成功",
                            "preview",
                            "预览",
                            "编辑",
                            "标题",
                            "描述",
                            "发布",
                            "img",  # 图片预览
                            "thumbnail",  # 缩略图
                        ]
                        
                        # 检查是否出现了上传成功的指标
                        for indicator in success_indicators:
                            if indicator in current_page_content.lower() and indicator not in initial_page_content.lower():
                                upload_success = True
                                logger.info(f"检测到上传成功指标: {indicator}")
                                break
                        
                        # 检查是否还在显示"拖拽图片到此"（说明还在上传界面）
                        if "拖拽图片到此" in current_page_content or "点击上传" in current_page_content:
                            logger.info(f"仍在上传界面，继续等待... ({waited_time}s)")
                        else:
                            # 页面已经改变，可能是进入了编辑界面
                            upload_success = True
                            logger.info("页面已离开上传界面，可能上传成功")
                            break
                            
                    except Exception as e:
                        logger.warning(f"检查页面状态时出错: {e}")
                        continue
                
                if upload_success:
                    msg = f'文件上传成功并已进入编辑界面: {path}'
                    logger.info(msg)
                    return ActionResult(extracted_content=msg, include_in_memory=True)
                else:
                    msg = f'文件设置成功但上传可能未完成，页面未发生预期变化: {path}'
                    logger.warning(msg)
                    return ActionResult(error=msg)
                    
            except Exception as e:
                msg = f'上传文件时出错 index {index}: {str(e)}'
                logger.info(msg)
                return ActionResult(error=msg)

    @time_execution_sync('--act')
    async def act(
            self,
            action: ActionModel,
            browser_context: Optional[BrowserContext] = None,
            #
            page_extraction_llm: Optional[BaseChatModel] = None,
            sensitive_data: Optional[Dict[str, str]] = None,
            available_file_paths: Optional[list[str]] = None,
            #
            context: Context | None = None,
    ) -> ActionResult:
        """Execute an action"""

        try:
            for action_name, params in action.model_dump(exclude_unset=True).items():
                if params is not None:
                    if action_name.startswith("mcp"):
                        # this is a mcp tool
                        logger.debug(f"Invoke MCP tool: {action_name}")
                        mcp_tool = self.registry.registry.actions.get(action_name).function
                        result = await mcp_tool.ainvoke(params)
                    else:
                        result = await self.registry.execute_action(
                            action_name,
                            params,
                            browser=browser_context,
                            page_extraction_llm=page_extraction_llm,
                            sensitive_data=sensitive_data,
                            available_file_paths=available_file_paths,
                            context=context,
                        )

                    if isinstance(result, str):
                        return ActionResult(extracted_content=result)
                    elif isinstance(result, ActionResult):
                        return result
                    elif result is None:
                        return ActionResult()
                    else:
                        raise ValueError(f'Invalid action result type: {type(result)} of {result}')
            return ActionResult()
        except Exception as e:
            raise e

    async def setup_mcp_client(self, mcp_server_config: Optional[Dict[str, Any]] = None):
        self.mcp_server_config = mcp_server_config
        if self.mcp_server_config:
            self.mcp_client = await setup_mcp_client_and_tools(self.mcp_server_config)
            self.register_mcp_tools()

    def register_mcp_tools(self):
        """
        Register the MCP tools used by this controller.
        """
        if self.mcp_client:
            for server_name in self.mcp_client.server_name_to_tools:
                for tool in self.mcp_client.server_name_to_tools[server_name]:
                    tool_name = f"mcp.{server_name}.{tool.name}"
                    self.registry.registry.actions[tool_name] = RegisteredAction(
                        name=tool_name,
                        description=tool.description,
                        function=tool,
                        param_model=create_tool_param_model(tool),
                    )
                    logger.info(f"Add mcp tool: {tool_name}")
                logger.debug(
                    f"Registered {len(self.mcp_client.server_name_to_tools[server_name])} mcp tools for {server_name}")
        else:
            logger.warning(f"MCP client not started.")

    async def close_mcp_client(self):
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
