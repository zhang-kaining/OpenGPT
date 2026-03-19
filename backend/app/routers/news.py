from fastapi import APIRouter
from app.services.rss_news import get_news

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def list_news():
    items = await get_news()
    return {"items": items}
