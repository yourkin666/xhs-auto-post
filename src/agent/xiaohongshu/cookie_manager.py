#!/usr/bin/env python3
"""
小红书Cookie管理工具
"""
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class XiaohongshuCookieManager:
    """小红书Cookie管理类"""
    
    def __init__(self, cookie_dir: str = "./tmp/cookies"):
        """
        初始化Cookie管理器
        
        Args:
            cookie_dir: Cookie存储目录
        """
        self.cookie_dir = Path(cookie_dir)
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = self.cookie_dir / "xiaohongshu_cookies.json"
        
    def load_cookies_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        从文件加载cookies
        
        Args:
            file_path: cookie文件路径
            
        Returns:
            cookies列表
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Cookie文件不存在: {file_path}")
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            # 支持多种格式
            if content.startswith('['):
                # JSON数组格式
                cookies = json.loads(content)
            elif content.startswith('{'):
                # JSON对象格式
                data = json.loads(content)
                if 'cookies' in data:
                    cookies = data['cookies']
                else:
                    cookies = [data]
            else:
                # Netscape格式或其他格式
                cookies = self._parse_netscape_cookies(content)
            
            # 验证和清理cookies
            valid_cookies = []
            for cookie in cookies:
                if self._validate_cookie(cookie):
                    # 确保必需字段存在
                    if 'domain' not in cookie:
                        cookie['domain'] = '.xiaohongshu.com'
                    if 'path' not in cookie:
                        cookie['path'] = '/'
                    if 'secure' not in cookie:
                        cookie['secure'] = True
                    valid_cookies.append(cookie)
            
            logger.info(f"成功加载 {len(valid_cookies)} 个有效cookies")
            return valid_cookies
            
        except Exception as e:
            logger.error(f"加载cookies失败: {e}")
            return []
    
    def _parse_netscape_cookies(self, content: str) -> List[Dict[str, Any]]:
        """解析Netscape格式的cookies"""
        cookies = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            parts = line.split('\t')
            if len(parts) >= 7:
                cookie = {
                    'domain': parts[0],
                    'httpOnly': parts[1].lower() == 'true',
                    'path': parts[2],
                    'secure': parts[3].lower() == 'true',
                    'expires': int(parts[4]) if parts[4] != '0' else None,
                    'name': parts[5],
                    'value': parts[6]
                }
                cookies.append(cookie)
        
        return cookies
    
    def _validate_cookie(self, cookie: Dict[str, Any]) -> bool:
        """验证cookie是否有效"""
        required_fields = ['name', 'value']
        for field in required_fields:
            if field not in cookie:
                logger.warning(f"Cookie缺少必需字段: {field}")
                return False
        
        # 检查是否是小红书相关的cookie
        domain = cookie.get('domain', '')
        if 'xiaohongshu' not in domain and 'xhscdn' not in domain:
            # 如果没有域名信息，检查cookie名称
            name = cookie.get('name', '').lower()
            xiaohongshu_cookie_names = [
                'sessionid', 'userid', 'web_session', 'xsec_token',
                'a1', 'webid', 'gid', 'customerid', 'customerbeaconid'
            ]
            if not any(xhs_name in name for xhs_name in xiaohongshu_cookie_names):
                logger.debug(f"跳过非小红书cookie: {cookie.get('name')}")
                return False
        
        return True
    
    def save_cookies(self, cookies: List[Dict[str, Any]]) -> bool:
        """
        保存cookies到文件
        
        Args:
            cookies: cookies列表
            
        Returns:
            是否保存成功
        """
        try:
            cookie_data = {
                'cookies': cookies,
                'saved_at': datetime.now().isoformat(),
                'domain': 'xiaohongshu.com'
            }
            
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存 {len(cookies)} 个cookies到 {self.cookie_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")
            return False
    
    def load_saved_cookies(self) -> List[Dict[str, Any]]:
        """加载已保存的cookies"""
        if not self.cookie_file.exists():
            logger.info("未找到已保存的cookies")
            return []
        
        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cookies = data.get('cookies', [])
            saved_at = data.get('saved_at', 'unknown')
            logger.info(f"加载已保存的cookies ({saved_at}): {len(cookies)} 个")
            
            return cookies
            
        except Exception as e:
            logger.error(f"加载已保存的cookies失败: {e}")
            return []
    
    async def set_browser_cookies(self, browser_context, cookies: List[Dict[str, Any]]) -> bool:
        """
        将cookies设置到浏览器上下文
        
        Args:
            browser_context: 浏览器上下文
            cookies: cookies列表
            
        Returns:
            是否设置成功
        """
        try:
            if not cookies:
                logger.warning("没有cookies可设置")
                return False
            
            # 转换cookies格式以适配playwright
            playwright_cookies = []
            for cookie in cookies:
                playwright_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', '.xiaohongshu.com'),
                    'path': cookie.get('path', '/'),
                }
                
                # 可选属性
                if 'secure' in cookie:
                    playwright_cookie['secure'] = cookie['secure']
                if 'httpOnly' in cookie:
                    playwright_cookie['httpOnly'] = cookie['httpOnly']
                    
                # 处理过期时间
                if 'expires' in cookie and cookie['expires']:
                    try:
                        if isinstance(cookie['expires'], (int, float)):
                            playwright_cookie['expires'] = cookie['expires']
                        elif isinstance(cookie['expires'], str):
                            playwright_cookie['expires'] = int(cookie['expires'])
                    except:
                        pass  # 忽略无效的过期时间
                
                playwright_cookies.append(playwright_cookie)
            
            # 设置cookies - 使用成功验证的方法
            try:
                # 首先导航到域名以确保cookies可以被设置
                await browser_context.navigate_to("https://www.xiaohongshu.com")
                
                # 获取当前页面
                page = await browser_context.get_current_page()
                if not page:
                    logger.error("无法获取当前页面")
                    return False
                
                # 通过页面的context设置cookies
                await page.context.add_cookies(playwright_cookies)
                logger.info(f"成功设置 {len(playwright_cookies)} 个cookies到浏览器")
                
                # 刷新页面以应用cookies
                await page.reload()
                
                return True
                
            except Exception as e:
                logger.error(f"设置cookies失败: {e}")
                return False
            
        except Exception as e:
            logger.error(f"设置浏览器cookies失败: {e}")
            return False
    
    def extract_cookies_from_browser(self, browser_context) -> List[Dict[str, Any]]:
        """
        从浏览器上下文提取cookies
        
        Args:
            browser_context: 浏览器上下文
            
        Returns:
            cookies列表
        """
        try:
            # 获取所有cookies
            all_cookies = browser_context.cookies()
            
            # 过滤小红书相关的cookies
            xiaohongshu_cookies = []
            for cookie in all_cookies:
                domain = cookie.get('domain', '')
                if 'xiaohongshu' in domain or 'xhscdn' in domain:
                    xiaohongshu_cookies.append(cookie)
            
            logger.info(f"从浏览器提取到 {len(xiaohongshu_cookies)} 个小红书cookies")
            return xiaohongshu_cookies
            
        except Exception as e:
            logger.error(f"从浏览器提取cookies失败: {e}")
            return []
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的cookie文件格式"""
        return [
            "JSON数组格式 ([{...}, {...}])",
            "JSON对象格式 ({cookies: [...]})",
            "Netscape格式 (浏览器导出)",
            "EditThisCookie扩展格式",
            "Cookie Editor扩展格式"
        ]
    
    def print_usage_help(self):
        """打印使用帮助"""
        print("🍪 小红书Cookie管理工具")
        print("=" * 50)
        print()
        print("📋 支持的Cookie文件格式:")
        for fmt in self.get_supported_formats():
            print(f"  • {fmt}")
        print()
        print("📁 Cookie文件路径:")
        print(f"  • 默认保存路径: {self.cookie_file}")
        print(f"  • Cookie目录: {self.cookie_dir}")
        print()
        print("🔧 使用方法:")
        print("  1. 从浏览器导出cookies")
        print("  2. 将cookie文件放到指定位置")
        print("  3. 运行小红书Agent自动加载")
        print()
        print("💡 获取Cookies的方法:")
        print("  • 使用浏览器扩展: EditThisCookie, Cookie Editor")
        print("  • 使用开发者工具: Network -> Cookies")
        print("  • 使用浏览器导出功能")


def main():
    """主函数 - 用于测试cookie管理功能"""
    print("🍪 小红书Cookie管理工具测试")
    print("=" * 50)
    
    manager = XiaohongshuCookieManager()
    manager.print_usage_help()
    
    # 检查是否有已保存的cookies
    saved_cookies = manager.load_saved_cookies()
    if saved_cookies:
        print(f"\n✅ 找到已保存的cookies: {len(saved_cookies)} 个")
        
        # 显示部分cookie信息
        for i, cookie in enumerate(saved_cookies[:3]):
            name = cookie.get('name', 'unknown')
            domain = cookie.get('domain', 'unknown')
            print(f"  {i+1}. {name} @ {domain}")
        
        if len(saved_cookies) > 3:
            print(f"  ... 还有 {len(saved_cookies) - 3} 个")
    else:
        print("\n📁 未找到已保存的cookies")
        print("请将cookie文件放到以下位置之一:")
        print(f"  • {manager.cookie_file}")
        print(f"  • {manager.cookie_dir}/cookies.json")


if __name__ == "__main__":
    main() 