# 小红书登录配置
from typing import Dict, Any, List

class XiaohongshuLoginConfig:
    """小红书登录配置类"""
    
    @staticmethod
    def get_browser_config() -> Dict[str, Any]:
        """获取优化的浏览器配置"""
        return {
            "headless": False,  # 显示浏览器窗口，便于用户登录
            "window_width": 1280,
            "window_height": 720,
            "disable_security": True,  # 禁用安全限制
            "use_cookie_login": True,  # 启用cookie登录
            "cookie_file_path": "",  # cookie文件路径（空表示使用默认路径）
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "extra_browser_args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                "--disable-web-security",
                "--allow-running-insecure-content",
                "--disable-features=VizDisplayCompositor",
                "--flag-switches-begin --disable-site-isolation-trials --flag-switches-end",
            ]
        }
    
    @staticmethod
    def get_login_selectors() -> List[Dict[str, str]]:
        """获取可能的登录按钮选择器"""
        return [
            {"type": "text", "value": "登录"},
            {"type": "text", "value": "注册登录"},
            {"type": "text", "value": "登录/注册"},
            {"type": "class", "value": "login-btn"},
            {"type": "class", "value": "login-button"},
            {"type": "class", "value": "sign-in"},
            {"type": "class", "value": "auth-btn"},
            {"type": "xpath", "value": "//button[contains(text(), '登录')]"},
            {"type": "xpath", "value": "//a[contains(text(), '登录')]"},
            {"type": "xpath", "value": "//div[contains(text(), '登录')]"},
            {"type": "css", "value": "[data-testid='login-btn']"},
            {"type": "css", "value": "[data-cy='login']"},
        ]
    
    @staticmethod
    def get_login_success_indicators() -> List[str]:
        """获取登录成功的标识符"""
        return [
            "登录成功",
            "已登录", 
            "login successful",
            "logged in",
            "用户头像",
            "个人中心",
            "我的主页",
            "发布笔记",
            "创作中心",
            "关注",
            "粉丝",
            "获赞",
            "收藏",
            "用户名",
            "退出登录",
            "logout",
            "profile",
            "avatar"
        ]
    
    @staticmethod
    def get_login_failure_indicators() -> List[str]:
        """获取登录失败的标识符"""
        return [
            "登录失败",
            "login failed",
            "未找到登录",
            "无法登录",
            "登录按钮不存在",
            "element not found",
            "登录超时",
            "验证失败",
            "网络错误",
            "请重试",
            "验证码错误",
            "账号密码错误"
        ]
    
    @staticmethod
    def get_wait_conditions() -> Dict[str, int]:
        """获取等待条件配置"""
        return {
            "page_load_timeout": 30,  # 页面加载超时时间（秒）
            "element_wait_timeout": 10,  # 元素等待超时时间（秒）
            "login_wait_timeout": 60,  # 登录等待超时时间（秒）
            "verification_wait_timeout": 5,  # 验证等待超时时间（秒）
            "retry_interval": 2,  # 重试间隔（秒）
            "max_retries": 3,  # 最大重试次数
        }
    
    @staticmethod
    def get_anti_detection_config() -> Dict[str, Any]:
        """获取反检测配置"""
        return {
            "enable_stealth": True,
            "random_delays": True,
            "human_like_actions": True,
            "viewport_randomization": True,
            "user_agent_rotation": False,  # 暂时关闭，保持一致性
            "cookie_management": True,
            "session_persistence": True,
        }
    
    @staticmethod
    def get_debug_config() -> Dict[str, Any]:
        """获取调试配置"""
        return {
            "screenshot_on_error": True,
            "save_html_on_error": True,
            "detailed_logging": True,
            "step_by_step_screenshots": False,  # 可选：每步截图
            "console_logs": True,
            "network_logs": False,  # 可选：网络日志
        } 