from .cli import main as cli_main
from ..utils.logging import get_logger

logger = get_logger(__name__)


def main():
    return cli_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Program terminated.")
    except Exception as e:
        logger.error("Hata: %s", e, exc_info=True)
