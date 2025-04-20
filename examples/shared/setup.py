import logging

from pydantic import BaseModel


class LoggingConfig(BaseModel):
    LOGGER_NAME: str = "fastapi_mcp"
    LOG_FORMAT: str = "%(levelprefix)s %(asctime)s\t[%(name)s] %(message)s"
    LOG_LEVEL: str = logging.getLevelName(logging.DEBUG)

    version: int = 1
    disable_existing_loggers: bool = False
    formatters: dict = {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: dict = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    }
    loggers: dict = {
        "": {"handlers": ["default"], "level": LOG_LEVEL},  # Root logger
        "uvicorn": {"handlers": ["default"], "level": LOG_LEVEL},
        LOGGER_NAME: {"handlers": ["default"], "level": LOG_LEVEL},
    }


def setup_logging():
    from logging.config import dictConfig

    logging_config = LoggingConfig()
    dictConfig(logging_config.model_dump())