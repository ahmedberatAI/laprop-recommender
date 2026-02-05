try:
    from laprop.utils.console import safe_print
except Exception:
    def safe_print(*args, **kwargs):
        print(*args, **kwargs)

try:
    from laprop.app.main import main
except Exception:
    safe_print(
        "\n❌ Laprop import failed. Ensure sitecustomize.py is available or install in editable mode."
    )
    raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\n👋 Program sonlandırıldı!")
    except Exception as e:
        safe_print(f"\n❌ Hata: {e}")
        import traceback

        traceback.print_exc()
