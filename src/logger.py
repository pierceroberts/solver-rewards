"""Easy universal log configuration """

import logging.config
from logging import Logger

from src.config import config


# TODO - use this in every file that logs (and prints).
def set_log(name: str) -> Logger:
    """Removes redundancy when setting log in each file"""

    log = logging.getLogger(name)

    logging.config.fileConfig(
        fname=config.io_config.log_config_file.absolute(),
        disable_existing_loggers=False,
    )
    return log
