from .cli import main as cli_main
from ..utils.console import safe_print


def main():
    return cli_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n[INFO] Program terminated.")
    except Exception as e:
        safe_print(f"\n[ERROR] Hata: {e}")
        import traceback

        traceback.print_exc()
