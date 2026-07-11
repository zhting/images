"""Central logging configuration: console + rotating file.

First step of the print()->logging migration: the infrastructure and
the API error log land here; module-by-module print replacement follows
in the engineering-baseline pass (enforced later via ruff's T20 rule).
"""
import logging
import logging.handlers
import os


def setup(level: str = "INFO", log_dir: str = None) -> str:
    """Configure the root logger once. Returns the log file path."""
    root = logging.getLogger()
    if getattr(setup, "_configured", False):
        return getattr(setup, "_logfile", "")
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_dir is None:
        log_dir = os.environ.get("DEEPPHOTO_LOG_DIR", ".")
    logfile = ""
    try:
        os.makedirs(log_dir, exist_ok=True)
        logfile = os.path.join(log_dir, "deepphoto.log")
        fh = logging.handlers.RotatingFileHandler(
            logfile, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception as e:  # file logging is best-effort
        root.warning("file logging disabled: %s", e)

    setup._configured = True
    setup._logfile = logfile
    return logfile
