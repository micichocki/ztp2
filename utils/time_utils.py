import logging
import pytz
from datetime import datetime, timedelta
from typing import Optional

from config import APPROPRIATE_HOURS_START, APPROPRIATE_HOURS_END

logger = logging.getLogger(__name__)


class TimeUtils:
    @staticmethod
    def is_within_appropriate_hours(dt: datetime, timezone_str: str) -> bool:
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        local_tz = pytz.timezone(timezone_str)
        local_dt = dt.astimezone(local_tz)
        
        local_hour = local_dt.hour
        
        logger.info(f"Checking if {local_dt.isoformat()} (hour: {local_hour}) is within appropriate hours "
                    f"({APPROPRIATE_HOURS_START}-{APPROPRIATE_HOURS_END}) in timezone {timezone_str}")
        
        return APPROPRIATE_HOURS_START <= local_hour < APPROPRIATE_HOURS_END

    @staticmethod
    def get_next_appropriate_time(dt: datetime, timezone_str: str) -> datetime:
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        local_tz = pytz.timezone(timezone_str)
        local_dt = dt.astimezone(local_tz)
        
        logger.info(f"Finding next appropriate time for {local_dt.isoformat()} in timezone {timezone_str}")
        
        if local_dt.hour >= APPROPRIATE_HOURS_END or local_dt.hour < APPROPRIATE_HOURS_START:
            if local_dt.hour >= APPROPRIATE_HOURS_END:
                local_dt = local_dt + timedelta(days=1)
                logger.info(f"After hours: adding a day to schedule for tomorrow")
            
            local_dt = local_dt.replace(hour=APPROPRIATE_HOURS_START, minute=0, second=0, microsecond=0)
            logger.info(f"Adjusted to appropriate hours start: {local_dt.isoformat()}")
        
        utc_dt = local_dt.astimezone(pytz.UTC)
        logger.info(f"Next appropriate time in UTC: {utc_dt.isoformat()}")
        return utc_dt

    @staticmethod
    def parse_scheduled_time(scheduled_time: Optional[str], timezone: str) -> Optional[datetime]:
        if not scheduled_time:
            return None
            
        dt = datetime.fromisoformat(scheduled_time)
        if dt.tzinfo is None:
            local_tz = pytz.timezone(timezone)
            dt = local_tz.localize(dt)
            logger.info(f"Localized naive datetime to {timezone}: {dt.isoformat()}")
        
        return dt
