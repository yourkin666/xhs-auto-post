#!/usr/bin/env python3
"""
硅基流动API配置文件
"""
import os
from typing import Dict, Any, Optional

class SiliconFlowConfig:
    """硅基流动API配置类"""
    
    DEFAULT_ENDPOINT = "https://api.siliconflow.cn/v1"
    
    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """获取API密钥"""
        return (
            os.getenv("SILICONFLOW_API_KEY") or 
            os.getenv("SiliconFLOW_API_KEY") or
            os.getenv("SILICON_FLOW_API_KEY")
        )
    
    @classmethod
    def get_base_url(cls) -> str:
        """获取基础URL"""
        return (
            os.getenv("SILICONFLOW_ENDPOINT") or 
            os.getenv("SiliconFLOW_ENDPOINT") or
            os.getenv("SILICON_FLOW_ENDPOINT") or
            cls.DEFAULT_ENDPOINT
        )
    
    @classmethod
    def get_llm_config(cls, model_name: str = "deepseek-ai/DeepSeek-R1") -> Dict[str, Any]:
        """获取LLM配置"""
        api_key = cls.get_api_key()
        if not api_key:
            raise ValueError(
                "硅基流动API密钥未设置！请设置以下环境变量之一：\n"
                "- SILICONFLOW_API_KEY\n"
                "- SiliconFLOW_API_KEY\n"
                "- SILICON_FLOW_API_KEY"
            )
        
        return {
            "provider": "siliconflow",
            "model_name": model_name,
            "api_key": api_key,
            "base_url": cls.get_base_url(),
            "temperature": 0.1,
        }
    
    @classmethod
    def check_configuration(cls) -> bool:
        """检查配置是否正确"""
        try:
            config = cls.get_llm_config()
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_supported_models(cls) -> Dict[str, str]:
        """获取支持的模型列表"""
        return {
            "deepseek-ai/DeepSeek-R1": "DeepSeek R1 - 最新推理模型",
            "deepseek-ai/DeepSeek-V3": "DeepSeek V3 - 高性能对话模型",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B": "DeepSeek R1 蒸馏版 32B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B": "DeepSeek R1 蒸馏版 14B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": "DeepSeek R1 蒸馏版 7B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B": "DeepSeek R1 蒸馏版 1.5B",
            "deepseek-ai/DeepSeek-V2.5": "DeepSeek V2.5 - 稳定版本",
            "Qwen/Qwen2.5-72B-Instruct": "Qwen2.5 72B - 大规模语言模型",
            "Qwen/Qwen2.5-32B-Instruct": "Qwen2.5 32B - 中型语言模型",
            "Qwen/Qwen2.5-14B-Instruct": "Qwen2.5 14B - 小型语言模型",
            "Qwen/Qwen2.5-7B-Instruct": "Qwen2.5 7B - 轻量级模型",
            "Qwen/QwQ-32B-Preview": "QwQ 32B - 预览版本",
        }
    
    @classmethod
    def print_configuration_help(cls):
        """打印配置帮助信息"""
        print("🔧 硅基流动API配置指南")
        print("=" * 50)
        print()
        print("1. 获取API密钥：")
        print("   访问 https://siliconflow.cn/ 注册并获取API密钥")
        print()
        print("2. 设置环境变量：")
        print("   export SILICONFLOW_API_KEY=your_api_key_here")
        print("   # 或者")
        print("   export SiliconFLOW_API_KEY=your_api_key_here")
        print()
        print("3. 可选：设置自定义端点")
        print("   export SILICONFLOW_ENDPOINT=https://api.siliconflow.cn/v1")
        print()
        print("4. 支持的模型：")
        models = cls.get_supported_models()
        for model, desc in models.items():
            print(f"   - {model}")
            print(f"     {desc}")
        print()
        print("5. 验证配置：")
        print("   python -c \"from siliconflow_config import SiliconFlowConfig; SiliconFlowConfig.check_configuration()\"")
        print()


def main():
    """主函数 - 用于测试配置"""
    print("🚀 硅基流动API配置检查")
    print("=" * 50)
    
    config = SiliconFlowConfig()
    
    # 检查配置
    if config.check_configuration():
        print("✅ 配置检查通过")
        
        # 显示当前配置
        try:
            llm_config = config.get_llm_config()
            print(f"📝 当前配置:")
            print(f"   提供商: {llm_config['provider']}")
            print(f"   模型: {llm_config['model_name']}")
            print(f"   API密钥: {llm_config['api_key'][:10]}...{llm_config['api_key'][-4:]}")
            print(f"   端点: {llm_config['base_url']}")
            print(f"   温度: {llm_config['temperature']}")
        except Exception as e:
            print(f"❌ 获取配置时出错: {e}")
    else:
        print("❌ 配置检查失败")
        print()
        config.print_configuration_help()


if __name__ == "__main__":
    main() 