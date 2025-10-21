import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends, Header, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.providers.dreamifly_provider import DreamiflyProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

provider = DreamiflyProvider()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动中... {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"服务将在 http://localhost:{settings.NGINX_PORT} 上可用")
    logger.info(f"Web UI 测试界面已启用，请访问 http://localhost:{settings.NGINX_PORT}/")
    yield
    logger.info("应用关闭。")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

async def verify_api_key(authorization: Optional[str] = Header(None)):
    if settings.API_MASTER_KEY and settings.API_MASTER_KEY != "1":
        if not authorization or "bearer" not in authorization.lower():
            raise HTTPException(status_code=401, detail="需要 Bearer Token 认证。")
        token = authorization.split(" ")[-1]
        if token != settings.API_MASTER_KEY:
            raise HTTPException(status_code=403, detail="无效的 API Key。")

@app.post("/v1/images/generations", dependencies=[Depends(verify_api_key)])
async def image_generations(request: Request):
    """处理文生图请求"""
    try:
        request_data = await request.json()
        return await provider.generate_image(request_data)
    except Exception as e:
        logger.error(f"处理文生图请求时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")

@app.post("/v1/images/edits", dependencies=[Depends(verify_api_key)])
async def image_edits(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    model: Optional[str] = Form(None),
    style: Optional[str] = Form("无"),
    n: Optional[int] = Form(1),
    size: Optional[str] = Form("1024x1024"),
    steps: Optional[int] = Form(20)
):
    """处理图生图请求"""
    try:
        image_bytes = await image.read()
        request_data = {
            "prompt": prompt,
            "model": model,
            "style": style,
            "n": n,
            "size": size,
            "steps": steps
        }
        return await provider.generate_image(request_data, image_bytes=image_bytes)
    except Exception as e:
        logger.error(f"处理图生图请求时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")

@app.get("/v1/models", dependencies=[Depends(verify_api_key)])
async def list_models():
    return await provider.get_models()

@app.get("/v1/styles", dependencies=[Depends(verify_api_key)])
async def list_styles():
    return JSONResponse(content={"data": list(settings.STYLE_MAPPING.keys())})

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_ui():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="UI 文件 (static/index.html) 未找到。")
