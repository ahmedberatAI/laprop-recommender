from .cli import main as cli_main



def main():
    return cli_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nğŸ‘‹ Program sonlandÄ±rÄ±ldÄ±!")
    except Exception as e:
        print(f"\nâŒ Hata: {e}")
        import traceback

        traceback.print_exc()
