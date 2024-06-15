from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level='INFO',
           format="<red>{time:YYYY-MM-DD HH:mm:ss}</red>:<level>{level}</level>: <level>{message}</level>")
