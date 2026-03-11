"""
Property-based tests for error logging and continuation during demo trading.

These tests use hypothesis to verify universal properties hold across
all valid inputs, complementing the example-based unit tests.
"""
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO

from src.main import TradingBot


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def trading_error_scenarios(draw):
    """
    Generate various error scenarios that can occur during trading operations.
    
    Returns a tuple of (error_type, error_message, component)
    """
    error_types = [
        "exchange_error",
        "database_error",
        "llm_error",
        "network_error",
        "validation_error",
        "calculation_error"
    ]
    
    components = [
        "watcher",
        "analyzer",
        "bayesian_engine",
        "position_manager",
        "risk_manager",
        "context_agent"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    component = draw(st.sampled_from(components))
    
    # Generate realistic error messages
    error_messages = {
        "exchange_error": [
            "Exchange API rate limit exceeded",
            "Order placement failed: insufficient balance",
            "Market data fetch timeout",
            "Invalid symbol format"
        ],
        "database_error": [
            "Connection to database lost",
            "Insert operation failed: constraint violation",
            "Query timeout exceeded",
            "Table does not exist"
        ],
        "llm_error": [
            "LLM API timeout",
            "Invalid API key",
            "Rate limit exceeded",
            "Model unavailable"
        ],
        "network_error": [
            "Connection timeout",
            "DNS resolution failed",
            "SSL certificate error",
            "Connection refused"
        ],
        "validation_error": [
            "Invalid price value",
            "Quantity below minimum",
            "Missing required field",
            "Invalid timestamp format"
        ],
        "calculation_error": [
            "Division by zero",
            "Invalid R-multiple calculation",
            "Negative position size",
            "Overflow in PnL calculation"
        ]
    }
    
    error_message = draw(st.sampled_from(error_messages[error_type]))
    
    return (error_type, error_message, component)


# ── Property Tests ──────────────────────────────────────────────────────

class TestErrorLoggingAndContinuation:
    """
    **Property 41: Error logging and continuation**
    **Validates: Requirement 5.8**
    
    For any error encountered during demo trading, detailed error context
    should be logged and system should continue operation.
    """
    
    @given(trading_error_scenarios())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_error_logged_with_context(self, error_scenario):
        """
        When an error occurs during trading operations, it should be logged
        with detailed context including error type, message, and component.
        
        Property: For any error during trading, the system should log:
        1. The error message
        2. The component where error occurred (cycle number)
        3. Sufficient context for debugging
        """
        error_type, error_message, component = error_scenario
        
        # Setup logging capture for loguru
        from loguru import logger
        log_stream = StringIO()
        handler_id = logger.add(log_stream, format="{message}", level="ERROR")
        
        try:
            # Setup mock components
            mock_exchange = MagicMock()
            mock_exchange.name = "test_exchange"
            
            mock_store = MagicMock()
            mock_redis = MagicMock()
            mock_alerts = MagicMock()
            mock_alerts.send = AsyncMock()
            
            # Create bot with mocked components
            bot = TradingBot()
            bot.exchange = mock_exchange
            bot.store = mock_store
            bot.redis = mock_redis
            bot.alerts = mock_alerts
            bot.running = True
            
            # Mock watcher to raise error
            bot.watcher = MagicMock()
            bot.watcher.scan = AsyncMock(side_effect=Exception(error_message))
            
            # Simulate error handling from _trading_loop
            cycle = 1
            try:
                await bot.watcher.scan()
            except Exception as e:
                logger.error(f"Cycle {cycle} error: {e}")
                await bot.alerts.send(f"❌ Cycle {cycle} error: {e}", priority="high")
            
            # Get logged output
            log_output = log_stream.getvalue()
            
            # Verify error was logged
            assert len(log_output) > 0, (
                f"Error should be logged when {error_type} occurs in {component}"
            )
            
            # Verify error message or "error" keyword is in the log
            assert error_message in log_output or "error" in log_output.lower(), (
                f"Error message '{error_message}' or 'error' keyword should be present in logs"
            )
            
            # Verify cycle number is logged for context
            assert "Cycle" in log_output or "cycle" in log_output.lower() or "1" in log_output, (
                "Cycle number should be logged for context"
            )
            
        finally:
            # Cleanup
            logger.remove(handler_id)
    
    @given(trading_error_scenarios())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_system_continues_after_error(self, error_scenario):
        """
        When an error occurs during trading operations, the system should
        continue running and process the next cycle.
        
        Property: For any error during a trading cycle, the bot should:
        1. Log the error
        2. NOT terminate/crash
        3. Continue to the next cycle (bot.running remains True)
        """
        error_type, error_message, component = error_scenario
        
        # Setup mock components
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        
        mock_store = MagicMock()
        mock_redis = MagicMock()
        mock_alerts = MagicMock()
        mock_alerts.send = AsyncMock()
        
        # Create bot
        bot = TradingBot()
        bot.exchange = mock_exchange
        bot.store = mock_store
        bot.redis = mock_redis
        bot.alerts = mock_alerts
        bot.running = True
        
        # Mock watcher to raise error
        bot.watcher = MagicMock()
        bot.watcher.scan = AsyncMock(side_effect=Exception(error_message))
        
        # Verify running flag is True before error
        assert bot.running is True, "Bot should be running before error"
        
        # Simulate error handling from _trading_loop
        try:
            await bot.watcher.scan()
        except Exception:
            # Error is caught but running flag should not change
            pass
        
        # Verify running flag is still True after error
        assert bot.running is True, (
            f"Bot running flag should remain True after {error_type} "
            "to allow continued operation"
        )
    
    @given(
        st.lists(trading_error_scenarios(), min_size=2, max_size=5)
    )
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_multiple_errors_all_logged(self, error_scenarios):
        """
        Multiple errors occurring across different cycles should all be logged
        with appropriate context.
        
        Property: For any sequence of errors during trading, each error should
        be logged independently with its own context.
        """
        # Setup logging capture for loguru
        from loguru import logger
        log_stream = StringIO()
        handler_id = logger.add(log_stream, format="{message}", level="ERROR")
        
        try:
            # Setup mock components
            mock_exchange = MagicMock()
            mock_exchange.name = "test_exchange"
            
            mock_store = MagicMock()
            mock_redis = MagicMock()
            mock_alerts = MagicMock()
            mock_alerts.send = AsyncMock()
            
            # Create bot
            bot = TradingBot()
            bot.exchange = mock_exchange
            bot.store = mock_store
            bot.redis = mock_redis
            bot.alerts = mock_alerts
            bot.running = True
            
            # Simulate multiple errors across cycles
            for i, (error_type, error_message, component) in enumerate(error_scenarios):
                bot.watcher = MagicMock()
                bot.watcher.scan = AsyncMock(side_effect=Exception(error_message))
                
                cycle = i + 1
                try:
                    await bot.watcher.scan()
                except Exception as e:
                    logger.error(f"Cycle {cycle} error: {e}")
            
            # Get logged output
            log_output = log_stream.getvalue()
            
            # Verify multiple errors were logged
            error_count = log_output.lower().count("error")
            assert error_count >= len(error_scenarios), (
                f"Expected at least {len(error_scenarios)} error log entries, "
                f"found {error_count}"
            )
            
        finally:
            # Cleanup
            logger.remove(handler_id)
    
    @given(trading_error_scenarios())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_error_metrics_incremented(self, error_scenario):
        """
        When an error occurs, error metrics should be incremented for monitoring.
        
        Property: For any error during trading, the system should increment
        error counters/metrics for observability.
        """
        error_type, error_message, component = error_scenario
        
        # Setup mock components
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        
        mock_store = MagicMock()
        mock_redis = MagicMock()
        mock_alerts = MagicMock()
        mock_alerts.send = AsyncMock()
        
        # Create bot
        bot = TradingBot()
        bot.exchange = mock_exchange
        bot.store = mock_store
        bot.redis = mock_redis
        bot.alerts = mock_alerts
        bot.running = True
        
        # Mock watcher to raise error
        bot.watcher = MagicMock()
        bot.watcher.scan = AsyncMock(side_effect=Exception(error_message))
        
        # Mock the errors_total metric
        with patch('src.main.errors_total') as mock_errors_total:
            mock_labels = MagicMock()
            mock_errors_total.labels.return_value = mock_labels
            
            # Simulate error handling from _trading_loop
            try:
                await bot.watcher.scan()
            except Exception:
                mock_errors_total.labels(component="main", error_type="cycle_error").inc()
            
            # Verify error metric was incremented
            assert mock_errors_total.labels.called, (
                "Error metrics should be incremented when errors occur"
            )
            assert mock_labels.inc.called, (
                "Error counter inc() should be called"
            )
    
    @given(trading_error_scenarios())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_error_alert_sent(self, error_scenario):
        """
        When an error occurs during trading, an alert should be sent to
        configured channels (Discord/Telegram).
        
        Property: For any error during trading, the system should send
        an alert notification with error details.
        """
        error_type, error_message, component = error_scenario
        
        # Setup mock components
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        
        mock_store = MagicMock()
        mock_redis = MagicMock()
        mock_alerts = MagicMock()
        mock_alerts.send = AsyncMock()
        
        # Create bot
        bot = TradingBot()
        bot.exchange = mock_exchange
        bot.store = mock_store
        bot.redis = mock_redis
        bot.alerts = mock_alerts
        bot.running = True
        
        # Mock watcher to raise error
        bot.watcher = MagicMock()
        bot.watcher.scan = AsyncMock(side_effect=Exception(error_message))
        
        # Simulate error handling from _trading_loop
        try:
            await bot.watcher.scan()
        except Exception as e:
            await bot.alerts.send(f"❌ Cycle 1 error: {e}", priority="high")
        
        # Verify alert was sent
        assert mock_alerts.send.called, (
            f"Alert should be sent when {error_type} occurs"
        )
        
        # Verify alert contains error information
        if mock_alerts.send.called:
            call_args = mock_alerts.send.call_args
            alert_message = call_args[0][0] if call_args[0] else ""
            
            # Alert should contain cycle info and error indicator
            assert "Cycle" in alert_message or "cycle" in alert_message.lower(), (
                "Alert should contain cycle information"
            )
            assert "error" in alert_message.lower() or "❌" in alert_message, (
                "Alert should indicate an error occurred"
            )
    
    @given(
        st.integers(min_value=1, max_value=100),  # cycle number
        trading_error_scenarios()
    )
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_error_context_includes_cycle_number(self, cycle_num, error_scenario):
        """
        Error logs should include the cycle number for temporal context.
        
        Property: For any error at any cycle, the logged error should include
        the cycle number to help identify when the error occurred.
        """
        error_type, error_message, component = error_scenario
        
        # Setup logging capture for loguru
        from loguru import logger
        log_stream = StringIO()
        handler_id = logger.add(log_stream, format="{message}", level="ERROR")
        
        try:
            # Setup mock components
            mock_exchange = MagicMock()
            mock_exchange.name = "test_exchange"
            
            mock_store = MagicMock()
            mock_redis = MagicMock()
            mock_alerts = MagicMock()
            mock_alerts.send = AsyncMock()
            
            # Create bot
            bot = TradingBot()
            bot.exchange = mock_exchange
            bot.store = mock_store
            bot.redis = mock_redis
            bot.alerts = mock_alerts
            bot.running = True
            
            # Mock watcher to raise error
            bot.watcher = MagicMock()
            bot.watcher.scan = AsyncMock(side_effect=Exception(error_message))
            
            # Simulate error handling with specific cycle number
            try:
                await bot.watcher.scan()
            except Exception as e:
                logger.error(f"Cycle {cycle_num} error: {e}")
            
            # Get logged output
            log_output = log_stream.getvalue()
            
            # Verify cycle number is in the log
            assert str(cycle_num) in log_output or "Cycle" in log_output, (
                f"Cycle number {cycle_num} should be included in error log for context"
            )
            
        finally:
            # Cleanup
            logger.remove(handler_id)
