__all__ = ('EvieeBaseException', 'InvalidCacheLimit', 'StartupFailure')


class EvieeBaseException(Exception):
    """Eviee's Base Exception Class"""


class InvalidCacheLimit(EvieeBaseException):
    pass


class StartupFailure(EvieeBaseException):
    pass
