"""
Discord channel message fetcher.

Uses Discord's REST API directly via aiohttp — no bot framework needed.
Only requires a bot token with "Read Message History" permission.
"""

import aiohttp
from typing import Optional

DISCORD_API = "https://discord.com/api/v10"


class DiscordFetchError(RuntimeError):
    """Raised when a Discord channel fetch fails."""

    def __init__(self, channel_id: str, status_code: int | None, message: str):
        super().__init__(message)
        self.channel_id = channel_id
        self.status_code = status_code
        self.message = message


async def fetch_channel_messages(
    bot_token: str,
    channel_id: str,
    limit: int = 100,
) -> list[dict]:
    """
    Fetch up to `limit` messages from a Discord channel.

    Handles pagination automatically to fetch beyond the 100-per-request cap.
    Returns messages newest-first, each as a raw Discord message dict.
    """
    headers = {"Authorization": f"Bot {bot_token}"}
    all_messages: list[dict] = []
    before: Optional[str] = None

    async with aiohttp.ClientSession() as session:
        while len(all_messages) < limit:
            batch_size = min(100, limit - len(all_messages))
            url = f"{DISCORD_API}/channels/{channel_id}/messages?limit={batch_size}"
            if before:
                url += f"&before={before}"

            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise DiscordFetchError(
                        channel_id=channel_id,
                        status_code=resp.status,
                        message=(
                            f"Discord API error {resp.status} for channel {channel_id}: {body}"
                        ),
                    )
                batch = await resp.json()

            if not batch:
                break

            all_messages.extend(batch)
            before = batch[-1]["id"]

            if len(batch) < batch_size:
                break

    return all_messages


async def fetch_all_channels(
    bot_token: str,
    channel_ids: list[str],
    limit_per_channel: int = 100,
) -> dict[str, list[dict]]:
    """
    Fetch messages from multiple channels.
    Returns {channel_id: [messages]}.
    """
    results: dict[str, list[dict]] = {}
    for cid in channel_ids:
        results[cid] = await fetch_channel_messages(bot_token, cid, limit_per_channel)
    return results
