import logging

from kombu.exceptions import KombuError
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# What an unreachable message broker looks like to the code that queues a job.
BROKER_ERRORS = (KombuError, RedisError, OSError)


def enqueue(task, *args, **kwargs) -> bool:
    """Queue a background job without ever failing the request that asked for it.

    Returns False (after logging) if the broker is unreachable. Use it for work that can wait for the
    next scheduled run, such as a first YouTube sync: the user's action has already been saved.
    """
    try:
        task.delay(*args, **kwargs)
        return True
    except BROKER_ERRORS:
        logger.exception("Could not queue background task %s", getattr(task, "name", task))
        return False
