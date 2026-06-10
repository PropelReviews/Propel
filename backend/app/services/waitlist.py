from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waitlist import WaitlistSubscriber
from app.posthog_events import capture_event
from app.schemas.waitlist import WaitlistCreate, WaitlistRead


async def create_subscriber(
    session: AsyncSession, payload: WaitlistCreate
) -> WaitlistRead:
    email = payload.email.lower()

    subscriber = WaitlistSubscriber(email=email)
    session.add(subscriber)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="WAITLIST_EMAIL_ALREADY_EXISTS",
        ) from None
    await session.refresh(subscriber)

    # Fired only after a successful commit; drives the PostHog email workflow.
    capture_event(email, "waitlist_joined", {"email": email})

    return WaitlistRead.model_validate(subscriber)
