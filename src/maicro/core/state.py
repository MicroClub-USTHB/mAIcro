import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default path for the state file
STATE_FILE_PATH = Path("data/ingestion_state.json")


def load_state(file_path: Path = STATE_FILE_PATH) -> dict[str, str]:
    """Load the ingestion state from a JSON file. Returns an empty dict if the file doesn't exist."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse state file at {file_path}. Returning empty state.")
        return {}
    except Exception as e:
        logger.error(f"Error reading state file: {e}")
        return {}


def save_state(state: dict[str, str], file_path: Path = STATE_FILE_PATH) -> None:
    """Save the ingestion state to a JSON file."""
    # Ensure the directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving state file: {e}")


def get_last_ingested_message_id(channel_id: str, file_path: Path = STATE_FILE_PATH) -> Optional[str]:
    """Get the last ingested message ID for a specific channel. Returns None if not found."""
    state = load_state(file_path)
    return state.get(channel_id)


def update_last_ingested_message_id(channel_id: str, message_id: str, file_path: Path = STATE_FILE_PATH) -> None:
    """Update the last ingested message ID for a specific channel."""
    state = load_state(file_path)
    state[channel_id] = message_id
    save_state(state, file_path)
