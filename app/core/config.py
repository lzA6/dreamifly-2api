from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )

    APP_NAME: str = "dreamifly-2api"
    APP_VERSION: str = "1.0.0"
    DESCRIPTION: str = "一个将 dreamifly.com 图像生成功能转换为兼容 OpenAI 格式 API 的高性能代理。"

    API_MASTER_KEY: Optional[str] = None
    DREAMIFLY_AUTH_TOKEN: Optional[str] = None

    # --- 修改点 1: 延长请求超时时间 ---
    # 将超时时间从 300 秒增加到 600 秒 (10 分钟)
    API_REQUEST_TIMEOUT: int = 600

    # --- 新增点: 上游 API 并发限制 ---
    # 根据您的反馈，设置为 2
    UPSTREAM_CONCURRENCY_LIMIT: int = 2

    NGINX_PORT: int = 8088

    # 模型配置
    # 定义了所有可用的模型及其对应的上游名称
    MODEL_MAPPING: Dict[str, str] = {
        "dreamifly-qwen-image": "Qwen-Image",
        "dreamifly-qwen-edit": "Qwen-Image-Edit",
        "dreamifly-flux-dev": "Flux-Dev",
        "dreamifly-flux-krea": "Flux-Krea",
        "dreamifly-flux-kontext": "Flux-Kontext",
        "dreamifly-sdxl": "Wai-SDXL-V150",
    }
    DEFAULT_MODEL: str = "dreamifly-qwen-image"

    # 风格配置
    # 定义了所有可用的风格及其对应的提示词前缀
    STYLE_MAPPING: Dict[str, str] = {
        "无": "",
        "卡通": "cartoon style, ",
        "动漫": "anime style, ",
        "油画": "oil painting style, ",
        "线稿": "line art style, ",
        "矢量线条": "vector line style, ",
        "街机像素": "pixel art style, ",
        "乐高积木": "lego style, ",
        "Riso噪点插画": "risograph style, ",
        "现实风格": "realistic style, ",
        "布偶风格": "puppet style, ",
        "Emoji图标风格": "emoji icon style, ",
    }

settings = Settings()
