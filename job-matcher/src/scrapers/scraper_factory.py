import logging

from .workday_scraper import WorkdayScraper
from .greenhouse_scraper import GreenhouseScraper
from .lever_scraper import LeverScraper
from .custom_scraper import CustomScraper
from .custom_api_scraper import CustomAPIScraper

log = logging.getLogger(__name__)


def get_scraper(board_config):
    board_type = board_config.get("type", "").lower()
    name = board_config.get("name", "Unknown")

    if board_type == "workday":
        log.debug("Using WorkdayScraper for %s", name)
        return WorkdayScraper(board_config)
    elif board_type == "greenhouse":
        log.debug("Using GreenhouseScraper for %s", name)
        return GreenhouseScraper(board_config)
    elif board_type == "lever":
        log.debug("Using LeverScraper for %s", name)
        return LeverScraper(board_config)
    elif board_type == "custom-api":
        log.debug("Using CustomAPIScraper for %s", name)
        return CustomAPIScraper(board_config)
    elif board_type == "custom":
        log.debug("Using CustomScraper for %s", name)
        return CustomScraper(board_config)
    else:
        raise ValueError(f"Unknown board type '{board_type}' for {name}")
