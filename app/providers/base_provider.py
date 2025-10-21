from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi.responses import JSONResponse

class BaseProvider(ABC):
    @abstractmethod
    async def generate_image(self, request_data: Dict[str, Any], image_bytes: Optional[bytes] = None) -> JSONResponse:
        pass

    @abstractmethod
    async def get_models(self) -> JSONResponse:
        pass
