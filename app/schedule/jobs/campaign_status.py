import asyncio
import logging

from celery import shared_task

from app.db.base import create_scheduler_engine, create_scheduler_session_factory
from app.services.client.campaigns import campaign_service

logger = logging.getLogger(__name__)


@shared_task(name="app.schedule.jobs.campaign_status.refresh_statuses")
def refresh_statuses():
    """
    Periodic task to refresh campaign statuses based on Beijing time.
    """
    scheduler_engine = create_scheduler_engine()
    SchedulerSessionLocal = create_scheduler_session_factory(scheduler_engine)

    async def _run():
        async with SchedulerSessionLocal() as db:
            updated = await campaign_service.refresh_all_campaign_statuses(db)
            logger.info("Campaign status refresh completed (updated=%s)", updated)
            return updated

    try:
        updated = asyncio.run(_run())
        return {"updated": updated}
    except Exception:
        logger.exception("Campaign status refresh failed")
        raise
    finally:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scheduler_engine.dispose())
        finally:
            loop.close()
