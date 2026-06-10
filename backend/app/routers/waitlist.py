from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.waitlist import WaitlistCreate, WaitlistRead
from app.services import waitlist as waitlist_service

router = APIRouter(prefix="/api/v1", tags=["waitlist"])


@router.post("/waitlist", response_model=WaitlistRead, status_code=201)
async def join_waitlist(
    payload: WaitlistCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """Public landing-page waitlist signup (rate-limited per IP, no auth)."""
    return await waitlist_service.create_subscriber(session, payload)
