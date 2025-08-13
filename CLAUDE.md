# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

XHS-Auto-Post 是一个智能化的小红书（Xiaohongshu）内容自动发布工具。该项目使用浏览器自动化技术和大语言模型（LLM）来简化内容创建和发布流程。

## 开发命令

### 启动应用
```bash
python webui.py
```

启动 Gradio 网页界面，默认运行在 `http://127.0.0.1:7788`

### 命令行参数
```bash
python webui.py --ip 0.0.0.0 --port 8080 --theme Ocean
```

可选参数：
- `--ip`: 绑定的 IP 地址（默认：127.0.0.1）
- `--port`: 监听端口（默认：7788）
- `--theme`: UI 主题（可选：Default, Soft, Monochrome, Glass, Origin, Citrus, Ocean, Base）

### 安装依赖
```bash
pip install -r requirements.txt
```

## 核心架构

### 主要组件

1. **XiaohongshuAgent** (`src/agent/xiaohongshu/xiaohongshu_agent.py`)
   - 核心自动化代理，负责整个发帖流程
   - 集成 LLM 和浏览器控制
   - 管理内容扫描和发布任务

2. **CustomBrowser** (`src/browser/custom_browser.py`)
   - 封装 browser-use 库的浏览器配置
   - 支持自定义浏览器设置和用户数据

3. **CustomController** (`src/controller/custom_controller.py`)
   - 控制浏览器行为和自动化操作
   - 处理页面交互逻辑

4. **WebuiManager** (`src/webui/webui_manager.py`)
   - 管理 Gradio 界面状态和逻辑
   - 协调前端界面与后端服务

### 内容管理

- 内容存储目录：`tmp/xiaohongshu_posts/`
- 每个子文件夹代表一个帖子
- 每个帖子包含：
  - 图片文件（.png, .jpg, .jpeg）
  - 文案文件（.txt 或 .md）

### LLM 集成

支持多种 LLM 提供商：
- OpenAI (包括 Azure OpenAI)
- Anthropic Claude
- DeepSeek
- Google Gemini
- Alibaba Qwen
- Moonshot
- SiliconFlow
- 等其他提供商

### 配置管理

- 环境变量通过 `.env` 文件管理
- 浏览器和代理设置可通过 Web UI 配置
- 支持配置的保存和加载

## 重要技术细节

### 浏览器自动化
- 基于 `browser-use` 框架
- 支持 cookie 管理实现免登录
- 可配置无头模式或有界面模式

### 遥测禁用
项目明确禁用了所有遥测功能：
```python
os.environ['TELEMETRY_DISABLED'] = 'true'
os.environ['POSTHOG_DISABLED'] = 'true'
os.environ['DO_NOT_TRACK'] = '1'
os.environ['ANALYTICS_DISABLED'] = 'true'
os.environ['BROWSER_USE_TELEMETRY'] = 'false'
```

### 语言要求
根据 `.cursorrules` 文件要求：
- 所有对话、解释、注释和文档使用中文
- 代码注释使用中文
- 错误信息和用户界面文本使用中文

## 项目目录结构

```
src/
├── agent/xiaohongshu/     # 小红书代理相关
├── browser/               # 浏览器配置
├── controller/            # 控制器逻辑  
├── utils/                 # 工具类（配置、LLM提供商等）
└── webui/                 # Web界面组件
    └── components/        # UI组件
tmp/
├── xiaohongshu_posts/     # 发帖内容存储
├── cookies/               # Cookie存储
├── downloads/             # 下载文件
├── record_videos/         # 录制视频
├── traces/               # 追踪日志
└── webui_settings/       # WebUI设置
```

## 开发注意事项

1. 项目使用 Python 3.8+
2. 主要依赖：browser-use, gradio, langchain 系列库
3. 所有用户界面文本和交互使用中文
4. 遵循项目的中文注释规范
5. 新功能开发应考虑 Web UI 的集成