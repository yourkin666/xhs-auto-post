#!/usr/bin/env python3
"""
验证小红书Cookie的简单脚本
"""
import json
import os
from datetime import datetime, timezone

def verify_cookies():
    """验证cookies文件和内容"""
    print("🍪 小红书Cookie验证工具")
    print("=" * 40)
    
    # 检查cookie文件
    cookie_paths = [
        "tmp/cookies/xiaohongshu_cookies.json",
        "../../../tmp/cookies/xiaohongshu_cookies.json"
    ]
    
    cookie_file = None
    for path in cookie_paths:
        if os.path.exists(path):
            cookie_file = path
            break
    
    if not cookie_file:
        print("❌ 未找到cookie文件")
        return False
    
    print(f"📁 找到cookie文件: {cookie_file}")
    
    # 读取并验证cookies
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cookies = data.get('cookies', [])
        print(f"📊 总共 {len(cookies)} 个cookies")
        
        # 检查关键cookies
        key_cookies = {
            'a1': '认证token',
            'web_session': 'Web会话',
            'webId': 'Web标识',
            'gid': '全局标识',
            'x-user-id-creator.xiaohongshu.com': '创建者用户ID',
            'access-token-creator.xiaohongshu.com': '创建者访问令牌',
            'galaxy_creator_session_id': '创建者会话ID'
        }
        
        print("\n🔍 关键Cookie检查:")
        found_keys = []
        for cookie in cookies:
            name = cookie.get('name', '')
            if name in key_cookies:
                found_keys.append(name)
                # 检查过期时间
                expires = cookie.get('expirationDate', 0)
                if expires:
                    expire_time = datetime.fromtimestamp(expires, tz=timezone.utc)
                    now = datetime.now(timezone.utc)
                    days_left = (expire_time - now).days
                    
                    if days_left > 0:
                        print(f"  ✅ {name}: {key_cookies[name]} (还有{days_left}天过期)")
                    else:
                        print(f"  ⚠️ {name}: {key_cookies[name]} (已过期)")
                else:
                    print(f"  ✅ {name}: {key_cookies[name]} (会话cookie)")
        
        # 统计结果
        print(f"\n📈 统计结果:")
        print(f"  • 找到关键cookies: {len(found_keys)}/{len(key_cookies)}")
        
        if len(found_keys) >= 3:
            print("  ✅ Cookie质量: 优秀")
            print("  🎉 可以正常使用cookie登录")
            return True
        elif len(found_keys) >= 2:
            print("  ⚠️ Cookie质量: 良好")
            print("  💡 建议重新导出完整的cookies")
            return True
        else:
            print("  ❌ Cookie质量: 不足")
            print("  💡 需要重新获取cookies")
            return False
            
    except Exception as e:
        print(f"❌ 验证cookie时出错: {e}")
        return False

if __name__ == "__main__":
    verify_cookies() 