"""
Unit tests for Alert Manager.
"""
import pytest
from unittest.mock import AsyncMock, patch
from src.alerts import AlertManager


class TestAlertManager:
    def test_init_no_channels(self):
        """Alert manager works with no channels configured."""
        am = AlertManager()
        assert am.discord_webhook is None
        assert am.telegram_token is None

    def test_rate_limits_configured(self):
        """Rate limits for each priority level."""
        am = AlertManager()
        assert am._rate_limit_seconds["critical"] == 0
        assert am._rate_limit_seconds["low"] > am._rate_limit_seconds["high"]

    @pytest.mark.asyncio
    async def test_send_no_channels(self):
        """Sending with no channels configured should not raise."""
        am = AlertManager()
        await am.send("test message", priority="medium")

    @pytest.mark.asyncio
    async def test_send_discord(self):
        """Discord webhook should be called."""
        am = AlertManager(discord_webhook="https://discord.com/api/webhooks/test")
        with patch.object(am, '_send_discord', new_callable=AsyncMock) as mock_discord:
            await am.send("test alert", priority="high")
            mock_discord.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Same message within rate window should be suppressed."""
        am = AlertManager(discord_webhook="https://discord.com/api/webhooks/test")
        with patch.object(am, '_send_discord', new_callable=AsyncMock) as mock_discord:
            await am.send("rate test", priority="low")  # 5 min window
            await am.send("rate test", priority="low")  # should be suppressed
            assert mock_discord.call_count == 1
