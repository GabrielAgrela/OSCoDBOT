from bot.web.run import run_app
from bot.core.window import enable_dpi_awareness


if __name__ == "__main__":
    # Ensure DPI awareness so captured pixels map to screen coordinates
    enable_dpi_awareness()
    run_app()
