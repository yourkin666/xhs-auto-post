# XHS-Auto-Post: AI-Powered Xiaohongshu Automation Tool

XHS-Auto-Post is an intelligent, automated content posting tool for Xiaohongshu (小红书). It leverages browser automation and Large Language Models (LLMs) to streamline your content creation and publishing workflow.

This tool provides a user-friendly web interface to manage and automate the process of logging into Xiaohongshu, creating posts with images and text, and publishing them based on content stored locally on your machine.

## ✨ Features

- **Automated Posting**: Automatically uploads and posts content (images and text) to Xiaohongshu.
- **Web-Based UI**: An intuitive Gradio-based web interface for easy configuration and operation.
- **Content Management**: Scans a local directory for posts. Each post is a folder containing images and a text file for the caption.
- **Flexible Browser Control**: Supports both headless and headed browser modes, and can be configured to use your own browser instance.
- **Cookie-Based Login**: Simplifies authentication by using browser cookies, avoiding the need for manual logins for each session.
- **LLM Integration**: Built with LangChain, allowing for the integration of various language models to potentially assist with content generation (e.g., writing captions, generating tags).
- **Task Control**: The posting task can be started, paused, resumed, and stopped directly from the UI.
- **Configurable**: Settings for the agent, browser, and configurations can be managed and saved through the web interface.

## 🚀 How It Works

The application operates through a `XiaohongshuAgent` which is responsible for the automation tasks. Here's a high-level overview of the process:

1.  **Initialization**: The agent is initialized with a language model (LLM) and browser configurations.
2.  **Content Scanning**: It scans a designated directory (e.g., `tmp/xiaohongshu_posts`) to find available content. Each subdirectory is treated as a single post, with image files (`.png`, `.jpg`, etc.) and a text file (`.txt`, `.md`) for the caption.
3.  **Browser Setup**: It launches a browser instance using `browser-use`. It can be configured to use existing browser user data and cookies for seamless login.
4.  **Login**: The agent navigates to Xiaohongshu and logs in. It primarily uses cookies to restore a logged-in session.
5.  **Posting**: For each post found, the agent automates the steps of uploading the image(s) and pasting the text content into the post creation form on Xiaohongshu, and then publishes the post.
6.  **UI Updates**: The status of the posting process is reported back to the Gradio web UI in real-time.

## 🛠️ Getting Started

### Prerequisites

- Python 3.8+
- A modern web browser (e.g., Chrome, Edge)

### Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd xhs-auto-post
    ```

2.  **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  **Set up environment variables:**
    Create a `.env` file in the root directory of the project. This file is used for storing sensitive information like API keys for LLMs.

    ```
    # Example for OpenAI
    OPENAI_API_KEY="your-openai-api-key"
    OPENAI_API_BASE="your-openai-api-base-url" # Optional
    ```

2.  **Prepare content for posting:**
    - Inside the `tmp/xiaohongshu_posts` directory, create a new folder for each post you want to publish.
    - Place your image files and a text file (`.txt` or `.md`) containing the post's caption inside each folder.

## ▶️ Usage

To start the application, run the `webui.py` script from the root of the project:

```bash
python webui.py
```

This will launch the Gradio web server. You can access the UI by opening the provided URL (by default, `http://127.0.0.1:7788`) in your web browser.

From the UI, you can:

- Adjust agent and browser settings.
- Start, pause, or stop the posting process.
- View logs and the status of the posting tasks.

## 📂 Project Structure

Here is a brief overview of the key files and directories in the project:

```
xhs-auto-post/
├── .env                  # Environment variables (you need to create this)
├── requirements.txt      # Python dependencies
├── webui.py              # Main entry point to launch the Gradio web UI
├── src/
│   ├── agent/
│   │   └── xiaohongshu/
│   │       ├── xiaohongshu_agent.py   # Core logic for the Xiaohongshu agent
│   │       ├── cookie_manager.py      # Manages Xiaohongshu login cookies
│   │       └── ...
│   ├── browser/
│   │   └── custom_browser.py        # Custom browser configurations
│   ├── controller/
│   │   └── custom_controller.py     # Controls browser actions
│   ├── utils/
│   │   ├── config.py                # Configuration handling
│   │   └── llm_provider.py          # Provides LLM instances
│   └── webui/
│       ├── interface.py             # Defines the Gradio UI layout and components
│       ├── webui_manager.py         # Manages the state and logic of the UI
│       └── components/              # Individual tabs/components of the UI
└── tmp/
    └── xiaohongshu_posts/           # Default directory for post content
```
