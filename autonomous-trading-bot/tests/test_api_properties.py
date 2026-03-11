"""
Property-based tests for API integration components.

These tests use hypothesis to verify universal properties hold across
all valid inputs, complementing the example-based unit tests.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings
import httpx

from src.gateio_testnet import GateIOTestnetConnector


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def api_failure_scenario(draw):
    """Generate API failure scenarios with different error types and attempt counts."""
    # Number of failures before success (0 means immediate success)
    failures_before_success = draw(st.integers(min_value=0, max_value=5))
    
    # Error type
    error_type = draw(st.sampled_from([
        "http_status_error",
        "timeout",
        "connection_error",
        "generic_exception"
    ]))
    
    # HTTP status code for status errors
    status_code = draw(st.sampled_from([500, 502, 503, 504, 429]))
    
    return {
        "failures_before_success": failures_before_success,
        "error_type": error_type,
        "status_code": status_code
    }


# ── Property Tests ──────────────────────────────────────────────────────

class TestExponentialBackoffRetry:
    """
    **Property 4: Exponential backoff retry**
    **Validates: Requirement 2.8**
    
    For any API call that fails, the retry delay should increase exponentially
    (delay_n = base_delay * 2^n) up to max_retries attempts.
    """
    
    @given(api_failure_scenario())
    @settings(max_examples=10, deadline=None)
    def test_exponential_backoff_delay_formula(self, scenario):
        """
        Retry delays must follow exponential backoff formula: delay_n = base_delay * 2^n
        where n is the attempt number (0-indexed).
        """
        connector = GateIOTestnetConnector(
            api_key="test_key",
            secret_key="test_secret",
            testnet_url="https://api-testnet.gateapi.io/api/v4"
        )
        
        failures_before_success = scenario["failures_before_success"]
        error_type = scenario["error_type"]
        status_code = scenario["status_code"]
        
        # Track actual sleep delays
        actual_delays = []
        
        # Mock asyncio.sleep to capture delays
        async def mock_sleep(delay):
            actual_delays.append(delay)
            # Don't actually sleep in tests - just return immediately
            return None
        
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = "Test error"
        mock_response.json.return_value = {"status": "success"}
        
        # Track call count
        call_count = [0]
        
        async def mock_request(*args, **kwargs):
            call_count[0] += 1
            
            # Fail for the first N attempts, then succeed
            if call_count[0] <= failures_before_success:
                if error_type == "http_status_error":
                    raise httpx.HTTPStatusError(
                        "Test error",
                        request=MagicMock(),
                        response=mock_response
                    )
                elif error_type == "timeout":
                    raise httpx.TimeoutException("Test timeout")
                elif error_type == "connection_error":
                    raise httpx.ConnectError("Test connection error")
                else:
                    raise Exception("Test generic error")
            else:
                # Success case
                return mock_response
        
        # Run the test
        async def run_test():
            with patch('asyncio.sleep', mock_sleep):
                with patch('httpx.AsyncClient') as mock_client:
                    # Setup mock client
                    mock_instance = AsyncMock()
                    mock_client.return_value.__aenter__.return_value = mock_instance
                    mock_instance.get = mock_request
                    mock_instance.post = mock_request
                    
                    try:
                        # Attempt API call
                        result = await connector._request_with_retry(
                            method="GET",
                            endpoint="/test",
                            params={"test": "param"}
                        )
                        
                        # If we got here, the call eventually succeeded
                        # Verify the delays followed exponential backoff
                        base_delay = connector.base_retry_delay
                        
                        for attempt_num, actual_delay in enumerate(actual_delays):
                            expected_delay = base_delay * (2 ** attempt_num)
                            
                            assert actual_delay == expected_delay, (
                                f"Delay for attempt {attempt_num} doesn't follow exponential backoff. "
                                f"Expected: {expected_delay}s (base={base_delay} * 2^{attempt_num}), "
                                f"Actual: {actual_delay}s"
                            )
                        
                        # Verify we retried the correct number of times
                        expected_retries = min(failures_before_success, connector.max_retries - 1)
                        assert len(actual_delays) == expected_retries, (
                            f"Expected {expected_retries} retry delays, got {len(actual_delays)}"
                        )
                        
                    except Exception as e:
                        # If max retries exceeded, verify we attempted max_retries times
                        if failures_before_success >= connector.max_retries:
                            assert call_count[0] == connector.max_retries, (
                                f"Should have attempted {connector.max_retries} times before giving up, "
                                f"but attempted {call_count[0]} times"
                            )
                            
                            # Verify delays followed exponential backoff for all retries
                            base_delay = connector.base_retry_delay
                            expected_num_delays = connector.max_retries - 1  # No delay after last attempt
                            
                            assert len(actual_delays) == expected_num_delays, (
                                f"Expected {expected_num_delays} retry delays, got {len(actual_delays)}"
                            )
                            
                            for attempt_num, actual_delay in enumerate(actual_delays):
                                expected_delay = base_delay * (2 ** attempt_num)
                                assert actual_delay == expected_delay, (
                                    f"Delay for attempt {attempt_num} doesn't follow exponential backoff. "
                                    f"Expected: {expected_delay}s, Actual: {actual_delay}s"
                                )
                        else:
                            # Unexpected error
                            raise
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=10, deadline=None)
    def test_max_retries_limit_enforced(self, failures_count):
        """
        API calls should not retry more than max_retries times, regardless of
        how many failures occur.
        """
        connector = GateIOTestnetConnector(
            api_key="test_key",
            secret_key="test_secret",
            testnet_url="https://api-testnet.gateapi.io/api/v4"
        )
        
        # Track call count
        call_count = [0]
        
        # Mock response that always fails
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Test error"
        
        async def mock_request(*args, **kwargs):
            call_count[0] += 1
            raise httpx.HTTPStatusError(
                "Test error",
                request=MagicMock(),
                response=mock_response
            )
        
        async def run_test():
            # Mock sleep to avoid delays
            with patch('asyncio.sleep', AsyncMock()):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_instance = AsyncMock()
                    mock_client.return_value.__aenter__.return_value = mock_instance
                    mock_instance.get = mock_request
                    
                    try:
                        await connector._request_with_retry(
                            method="GET",
                            endpoint="/test"
                        )
                    except httpx.HTTPStatusError:
                        # Expected to fail after max retries
                        pass
                    
                    # Verify we attempted exactly max_retries times
                    assert call_count[0] == connector.max_retries, (
                        f"Should have attempted exactly {connector.max_retries} times, "
                        f"but attempted {call_count[0]} times"
                    )
        
        asyncio.run(run_test())
    
    @given(st.integers(min_value=0, max_value=2))
    @settings(max_examples=10, deadline=None)
    def test_successful_call_on_retry_stops_retrying(self, success_on_attempt):
        """
        If an API call succeeds on a retry attempt, no further retries should occur.
        """
        connector = GateIOTestnetConnector(
            api_key="test_key",
            secret_key="test_secret",
            testnet_url="https://api-testnet.gateapi.io/api/v4"
        )
        
        call_count = [0]
        actual_delays = []
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Test error"
        mock_response.json.return_value = {"status": "success"}
        
        async def mock_request(*args, **kwargs):
            call_count[0] += 1
            
            # Fail until success_on_attempt, then succeed
            if call_count[0] <= success_on_attempt:
                raise httpx.HTTPStatusError(
                    "Test error",
                    request=MagicMock(),
                    response=mock_response
                )
            else:
                return mock_response
        
        async def mock_sleep(delay):
            actual_delays.append(delay)
            return None
        
        async def run_test():
            with patch('asyncio.sleep', mock_sleep):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_instance = AsyncMock()
                    mock_client.return_value.__aenter__.return_value = mock_instance
                    mock_instance.get = mock_request
                    
                    result = await connector._request_with_retry(
                        method="GET",
                        endpoint="/test"
                    )
                    
                    # Verify we called exactly success_on_attempt + 1 times
                    assert call_count[0] == success_on_attempt + 1, (
                        f"Should have called {success_on_attempt + 1} times "
                        f"(failed {success_on_attempt} times, then succeeded), "
                        f"but called {call_count[0]} times"
                    )
                    
                    # Verify we had exactly success_on_attempt delays
                    assert len(actual_delays) == success_on_attempt, (
                        f"Should have {success_on_attempt} retry delays, "
                        f"got {len(actual_delays)}"
                    )
                    
                    # Verify result is the successful response
                    assert result == {"status": "success"}
        
        asyncio.run(run_test())
    
    @given(
        st.floats(min_value=0.1, max_value=10.0),  # base_delay
        st.integers(min_value=1, max_value=5)  # max_retries
    )
    @settings(max_examples=10, deadline=None)
    def test_exponential_backoff_with_custom_parameters(self, base_delay, max_retries):
        """
        Exponential backoff should work correctly with different base_delay and
        max_retries configurations.
        """
        connector = GateIOTestnetConnector(
            api_key="test_key",
            secret_key="test_secret",
            testnet_url="https://api-testnet.gateapi.io/api/v4"
        )
        
        # Override parameters
        connector.base_retry_delay = base_delay
        connector.max_retries = max_retries
        
        actual_delays = []
        call_count = [0]
        
        # Mock response that always fails
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service unavailable"
        
        async def mock_request(*args, **kwargs):
            call_count[0] += 1
            raise httpx.HTTPStatusError(
                "Service unavailable",
                request=MagicMock(),
                response=mock_response
            )
        
        async def mock_sleep(delay):
            actual_delays.append(delay)
            return None
        
        async def run_test():
            with patch('asyncio.sleep', mock_sleep):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_instance = AsyncMock()
                    mock_client.return_value.__aenter__.return_value = mock_instance
                    mock_instance.get = mock_request
                    
                    try:
                        await connector._request_with_retry(
                            method="GET",
                            endpoint="/test"
                        )
                    except httpx.HTTPStatusError:
                        pass  # Expected
                    
                    # Verify delays follow exponential backoff with custom base_delay
                    expected_num_delays = max_retries - 1
                    assert len(actual_delays) == expected_num_delays, (
                        f"Expected {expected_num_delays} delays, got {len(actual_delays)}"
                    )
                    
                    for attempt_num, actual_delay in enumerate(actual_delays):
                        expected_delay = base_delay * (2 ** attempt_num)
                        
                        # Allow small floating point tolerance
                        assert abs(actual_delay - expected_delay) < 0.001, (
                            f"Delay for attempt {attempt_num} incorrect. "
                            f"Expected: {expected_delay}s (base={base_delay} * 2^{attempt_num}), "
                            f"Actual: {actual_delay}s"
                        )
        
        asyncio.run(run_test())
    
    @given(st.sampled_from(["GET", "POST", "DELETE"]))
    @settings(max_examples=10, deadline=None)
    def test_exponential_backoff_applies_to_all_http_methods(self, http_method):
        """
        Exponential backoff retry logic should apply consistently to all HTTP methods
        (GET, POST, DELETE, etc.).
        """
        connector = GateIOTestnetConnector(
            api_key="test_key",
            secret_key="test_secret",
            testnet_url="https://api-testnet.gateapi.io/api/v4"
        )
        
        actual_delays = []
        call_count = [0]
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_response.json.return_value = {"status": "success"}
        
        async def mock_request(*args, **kwargs):
            call_count[0] += 1
            
            # Fail twice, then succeed
            if call_count[0] <= 2:
                raise httpx.HTTPStatusError(
                    "Internal server error",
                    request=MagicMock(),
                    response=mock_response
                )
            else:
                return mock_response
        
        async def mock_sleep(delay):
            actual_delays.append(delay)
            return None
        
        async def run_test():
            with patch('asyncio.sleep', mock_sleep):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_instance = AsyncMock()
                    mock_client.return_value.__aenter__.return_value = mock_instance
                    mock_instance.get = mock_request
                    mock_instance.post = mock_request
                    mock_instance.delete = mock_request
                    
                    result = await connector._request_with_retry(
                        method=http_method,
                        endpoint="/test",
                        data={"test": "data"} if http_method == "POST" else None
                    )
                    
                    # Verify exponential backoff was applied
                    assert len(actual_delays) == 2, (
                        f"Expected 2 retry delays for {http_method}, got {len(actual_delays)}"
                    )
                    
                    base_delay = connector.base_retry_delay
                    assert actual_delays[0] == base_delay * (2 ** 0), (
                        f"First delay incorrect for {http_method}"
                    )
                    assert actual_delays[1] == base_delay * (2 ** 1), (
                        f"Second delay incorrect for {http_method}"
                    )
        
        asyncio.run(run_test())
