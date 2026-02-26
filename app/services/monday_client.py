import requests
from app.config import settings
from app.utils.logger import logger


class MondayClientError(Exception):
    """Custom exception for Monday.com API errors."""
    pass


def fetch_board_items(board_id: str) -> list[dict]:
    """
    Fetch all items from a Monday.com board with cursor-based pagination.

    Args:
        board_id: The numeric ID of the board.

    Returns:
        List of item dicts from the board.

    Raises:
        MondayClientError: On API or network failures.
    """
    if not board_id or not board_id.strip().isdigit():
        raise MondayClientError(f"Invalid board_id: {board_id!r}")

    all_items: list[dict] = []
    cursor = None

    headers = {
        "Authorization": settings.MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2024-10",
    }

    while True:
        query = _build_query(board_id, cursor)
        try:
            response = requests.post(
                settings.MONDAY_API_URL,
                json={"query": query},
                headers=headers,
                timeout=settings.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise MondayClientError(f"Monday.com API request failed: {e}") from e

        data = response.json()

        # Check for GraphQL-level errors
        if "errors" in data:
            raise MondayClientError(f"Monday.com API errors: {data['errors']}")

        try:
            items_page = data["data"]["boards"][0]["items_page"]
        except (KeyError, IndexError, TypeError) as e:
            raise MondayClientError(
                f"Unexpected API response structure: {e}"
            ) from e

        items = items_page.get("items", [])
        all_items.extend(items)
        logger.info(f"Fetched {len(items)} items (total: {len(all_items)})")

        cursor = items_page.get("cursor")
        if not cursor:
            break

    return all_items


def _build_query(board_id: str, cursor: str | None = None) -> str:
    """Build the GraphQL query with optional cursor for pagination."""
    cursor_arg = f', cursor: "{cursor}"' if cursor else ""
    return f"""
    query {{
        boards(ids: {board_id}) {{
            items_page(limit: 500{cursor_arg}) {{
                cursor
                items {{
                    id
                    name
                    column_values {{
                        text
                        column {{ title }}
                    }}
                }}
            }}
        }}
    }}
    """