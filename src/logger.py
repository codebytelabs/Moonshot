from loguru import logger
import sys

def setup_logging():
    logger.remove()
    logger.add(sys.stderr, level='INFO')
    logger.add('logs/bot.log', rotation='10 MB', retention='14 days', level='INFO')
    return logger
