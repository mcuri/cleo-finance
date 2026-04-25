import logging

logger = logging.getLogger("anthropic")


def log_usage(response, endpoint: str) -> None:
    model = response.model
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    logger.info(
        "model=%s input_tokens=%d output_tokens=%d endpoint=%s",
        model, input_tokens, output_tokens, endpoint,
    )

    try:
        from backend.sheets import SheetsClient
        from backend.config import get_settings
        sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
        sheets.append_log(endpoint, model, input_tokens, output_tokens)
    except Exception as exc:
        logger.warning("Failed to log to Sheets: %s", exc)
