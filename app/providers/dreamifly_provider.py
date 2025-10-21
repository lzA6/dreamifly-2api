import time
import logging
import random
import asyncio
import base64
import json
from typing import Dict, Any, Optional, Tuple

import cloudscraper
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

class DreamiflyProvider(BaseProvider):
    BASE_URL = "https://dreamifly.com/api/generate"

    def __init__(self):
        # --- 修改点 2: 初始化并发控制器 (Semaphore) ---
        # 使用在 config.py 中定义的值 (2)
        self.semaphore = asyncio.Semaphore(settings.UPSTREAM_CONCURRENCY_LIMIT)
        logger.info(f"并发控制器已初始化，最大并发数: {settings.UPSTREAM_CONCURRENCY_LIMIT}")

    def _prepare_headers(self) -> Dict[str, str]:
        if not settings.DREAMIFLY_AUTH_TOKEN:
            raise ValueError("DREAMIFLY_AUTH_TOKEN 未在 .env 文件中配置。")
        return {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Authorization": settings.DREAMIFLY_AUTH_TOKEN,
            "Content-Type": "application/json",
            "Origin": "https://dreamifly.com",
            "Referer": "https://dreamifly.com/zh",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }

    def _parse_size(self, size: Optional[str]) -> Tuple[int, int]:
        if not size or 'x' not in size:
            return 1024, 1024
        try:
            width, height = map(int, size.split('x'))
            return width, height
        except (ValueError, TypeError):
            logger.warning(f"无效的 size 参数: '{size}', 使用默认值 1024x1024")
            return 1024, 1024

    async def _send_single_request(self, payload: Dict[str, Any], task_id: int) -> str:
        # 保持每个请求创建独立 scraper 实例，确保线程安全
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        
        loop = asyncio.get_running_loop()
        headers = self._prepare_headers()
        
        logger.info(f"[任务 {task_id}] 正在向上游发送请求, Prompt: '{str(payload.get('prompt'))[:50]}...'")
        
        response = None
        try:
            response = await loop.run_in_executor(
                None, 
                lambda: scraper.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=settings.API_REQUEST_TIMEOUT
                )
            )
            
            logger.info(f"[任务 {task_id}] 收到上游响应状态码: {response.status_code}")
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            
            if "application/json" in content_type:
                response_json = response.json()
                image_url = response_json.get("imageUrl")
                if not image_url or not image_url.startswith("data:image/png;base64,"):
                    raise ValueError(f"上游 API 返回的 JSON 中未包含有效的 Base64 图像数据。")
                logger.info(f"[任务 {task_id}] 成功获取图像数据。")
                return image_url.split(',', 1)[1]
            
            else:
                raise ValueError(f"上游返回了非预期的 Content-Type: {content_type}。可能是被 Cloudflare 拦截。")

        except Exception as e:
            error_message = f"[任务 {task_id}] 请求上游失败: {e}"
            if response is not None:
                error_message += f"\n上游响应内容 (Raw Text):\n---START---\n{response.text[:1000]}\n---END---"
            logger.error(error_message, exc_info=True)
            raise

    async def generate_image(self, request_data: Dict[str, Any], image_bytes: Optional[bytes] = None) -> JSONResponse:
        prompt = request_data.get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="参数 'prompt' 不能为空。")

        user_model = request_data.get("model", settings.DEFAULT_MODEL)
        actual_model = settings.MODEL_MAPPING.get(user_model)
        if not actual_model:
            raise HTTPException(status_code=400, detail=f"不支持的模型: '{user_model}'")

        style_key = request_data.get("style", "无")
        style_prefix = settings.STYLE_MAPPING.get(style_key, "")
        final_prompt = f"{style_prefix}{prompt}"

        width, height = self._parse_size(request_data.get("size"))
        num_images = request_data.get("n", 1)
        steps = request_data.get("steps", 20)

        base_payload = {
            "prompt": final_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "batch_size": 1,
            "model": actual_model,
        }

        if image_bytes:
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            base_payload["images"] = [f"data:image/png;base64,{base64_image}"]
            if "edit" not in actual_model.lower():
                 logger.warning(f"正在使用参考图，但选择的模型 '{actual_model}' 可能不是一个编辑模型。")
        else:
            base_payload["images"] = []

        # --- 修改点 3: 使用并发控制器包装任务 ---
        async def controlled_task_runner(payload: Dict[str, Any], task_id: int):
            """一个包装器，它会先获取信号量，再执行任务"""
            async with self.semaphore:
                logger.info(f"[任务 {task_id}] 获取到信号量，开始执行。")
                result = await self._send_single_request(payload, task_id)
                logger.info(f"[任务 {task_id}] 执行完毕，释放信号量。")
                return result

        tasks = []
        for i in range(num_images):
            payload = base_payload.copy()
            payload["seed"] = random.randint(0, 100_000_000)
            # 创建被并发控制器包装后的任务
            tasks.append(controlled_task_runner(payload, task_id=i + 1))
        
        logger.info(f"已创建 {num_images} 个任务，准备通过并发控制器（上限 {settings.UPSTREAM_CONCURRENCY_LIMIT}）执行...")

        try:
            # asyncio.gather 会并发运行所有任务，但 semaphore 会确保同时进行的网络请求不超过限制
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            exceptions = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error(f"[任务 {i + 1}] 最终执行失败: {res}")
                    exceptions.append(f"任务 {i+1}: {res}")
                else:
                    successful_results.append({"b64_json": res})
            
            if not successful_results:
                error_details = "; ".join(exceptions)
                raise HTTPException(status_code=502, detail=f"所有上游图像生成任务均失败。错误详情: {error_details}")

            return JSONResponse(content={
                "created": int(time.time()),
                "data": successful_results
            })

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"处理并发请求时发生严重错误: {e}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"上游服务错误或所有重试均失败: {str(e)}")

    async def get_models(self) -> JSONResponse:
        return JSONResponse(content={
            "object": "list",
            "data": [
                {"id": name, "object": "model", "created": int(time.time()), "owned_by": "lzA6"}
                for name in settings.MODEL_MAPPING.keys()
            ]
        })
