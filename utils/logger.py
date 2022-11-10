# WIP (unused)
import logging
import logging.handlers
import sys
import datetime

class Log:
    def set_logger(name=None):
        # stdout handler
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.addFilter(lambda record: record.levelno == logging.INFO)
        stdout_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(funcName)s <%(filename)s> (%(lineno)s) : [%(levelname)s] %(message)s", '%Y-%m-%d %H:%M:%S')
        )

        # stderror handler
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(funcName)s <%(filename)s> (%(lineno)s) : [%(levelname)s] %(message)s", '%Y-%m-%d %H:%M:%S')
        )

        # log file handler
        file_handler = logging.handlers.RotatingFileHandler("log/bot_log.txt", maxBytes=100000, backupCount=10)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("[%(asctime)s][%(levelname)s] %(funcName)s <%(filename)s> (%(lineno)s) : %(message)s")
        )

        # set handler
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)
        logger.addHandler(stderr_handler)
        logger.addHandler(file_handler)
    
    def get_logger(name=None):
        return logging.getLogger(name)