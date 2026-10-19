"""Raised when trust_config.json is missing a key the code needs.

There is no fallback value. A missing key is a configuration error.
"""


class ConfigError(RuntimeError):
    pass
