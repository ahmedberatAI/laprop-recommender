from pathlib import Path
import sys

# Keep BASE_DIR aligned with legacy behavior (project root)
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if SRC_DIR.exists():
    src_str = str(SRC_DIR)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

try:
    from laprop.app.main import main
except Exception as e:
    print("\nâŒ Laprop import failed. Ensure src is on sys.path and dependencies are installed.")
    raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nğŸ‘‹ Program sonlandÄ±rÄ±ldÄ±!")
    except Exception as e:
        print(f"\nâŒ Hata: {e}")
        import traceback

        traceback.print_exc()
