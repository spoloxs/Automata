# automata/web-agent/src/web_agent/util/logger.py

import datetime
import sys


class LogColors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    INFO = "\033[38;5;39m"
    DEBUG = "\033[38;5;244m"
    SUCCESS = "\033[38;5;82m"
    TIME = "\033[38;5;245m"


def _timestamp():
    now = datetime.datetime.now()
    return f"{LogColors.TIME}{now.strftime('%Y-%m-%d %H:%M:%S')}{LogColors.ENDC}"


def log_info(msg):
    print(f"{_timestamp()} {LogColors.INFO}[INFO]{LogColors.ENDC} {msg}")


def log_warn(msg):
    print(f"{_timestamp()} {LogColors.WARNING}[WARN]{LogColors.ENDC} {msg}")


def log_error(msg):
    print(
        f"{_timestamp()} {LogColors.FAIL}[ERROR]{LogColors.ENDC} {msg}", file=sys.stderr
    )


def log_debug(msg):
    print(f"{_timestamp()} {LogColors.DEBUG}[DEBUG]{LogColors.ENDC} {msg}")


def log_success(msg):
    print(f"{_timestamp()} {LogColors.SUCCESS}[SUCCESS]{LogColors.ENDC} {msg}")


def log_header(msg):
    print(f"{_timestamp()} {LogColors.HEADER}[HEADER]{LogColors.ENDC} {msg}")


def log_bold(msg):
    print(f"{_timestamp()} {LogColors.BOLD}{msg}{LogColors.ENDC}")


def log_underline(msg):
    print(f"{_timestamp()} {LogColors.UNDERLINE}{msg}{LogColors.ENDC}")


# Example usage:
if __name__ == "__main__":
    log_info("This is an info message.")
    log_warn("This is a warning.")
    log_error("This is an error!")
    log_debug("Debug details here.")
    log_success("Operation completed successfully!")
    log_header("This is a header.")
    log_bold("This is bold text.")
    log_underline("This is underlined text.")
