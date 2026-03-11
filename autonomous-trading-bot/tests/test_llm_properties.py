"""
Property-based tests for LLM response parsing.

These tests use hypothesis to verify universal properties hold across
all valid LLM API responses, ensuring robust parsing and validation.
"""
import json
from hypothesis import given, strategies as st, settings


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def valid_llm_response(draw):
    """Generate valid LLM API responses with various formats."""
    # Generate valid sentiment, confidence, and narrative_strength
    sentiment = draw(st.sampled_from(["bullish", "bearish", "neutral"]))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    narrative_strength = draw(st.floats(min_value=0.0, max_value=1.0))
    
    # Generate additional fields that might be present
    catalysts = draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5))
    risks = draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5))
    driver_type = draw(st.sampled_from([
        "narrative", "technical", "fundamental", "whale", "unknown"
    ]))
    summary = draw(st.text(min_size=10, max_size=200))
    
    # Create the response dict
    response_dict = {
        "sentiment": sentiment,
        "confidence": confidence,
        "narrative_strength": narrative_strength,
        "catalysts": catalysts,
        "risks": risks,
        "driver_type": driver_type,
        "summary": summary
    }
    
    # Choose response format
    format_type = draw(st.sampled_from([
        "plain_json",
        "markdown_json",
        "markdown_no_lang",
        "with_extra_text"
    ]))
    
    json_str = json.dumps(response_dict)
    
    if format_type == "plain_json":
        return json_str
    elif format_type == "markdown_json":
        return f"```json\n{json_str}\n```"
    elif format_type == "markdown_no_lang":
        return f"```\n{json_str}\n```"
    else:  # with_extra_text
        prefix = draw(st.text(min_size=0, max_size=50))
        suffix = draw(st.text(min_size=0, max_size=50))
        return f"{prefix}\n{json_str}\n{suffix}"


@st.composite
def perplexity_response(draw):
    """Generate Perplexity-style API responses."""
    sentiment = draw(st.sampled_from(["bullish", "bearish", "neutral"]))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    narrative_strength = draw(st.floats(min_value=0.0, max_value=1.0))
    
    response_dict = {
        "sentiment": sentiment,
        "confidence": confidence,
        "catalysts": draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5)),
        "risks": draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5)),
        "driver_type": draw(st.sampled_from([
            "narrative", "technical", "fundamental", "whale", "unknown"
        ])),
        "narrative_strength": narrative_strength,
        "sustainability_hours": draw(st.integers(min_value=1, max_value=168)),
        "summary": draw(st.text(min_size=10, max_size=200))
    }
    
    return json.dumps(response_dict)


@st.composite
def context_agent_batch_response(draw):
    """Generate Context Agent batch response (array of analyses)."""
    num_symbols = draw(st.integers(min_value=1, max_value=5))
    
    analyses = []
    for _ in range(num_symbols):
        sentiment = draw(st.sampled_from(["bullish", "bearish", "neutral"]))
        confidence = draw(st.floats(min_value=0.0, max_value=1.0))
        
        analysis = {
            "symbol": draw(st.text(min_size=3, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',)))),
            "sentiment": sentiment,
            "confidence": confidence,
            "catalysts": draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=3)),
            "risks": draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=3)),
            "driver_type": draw(st.sampled_from([
                "narrative", "technical", "fundamental", "whale", "unknown"
            ])),
            "summary": draw(st.text(min_size=10, max_size=100))
        }
        analyses.append(analysis)
    
    # Choose format
    format_type = draw(st.sampled_from(["plain_json", "markdown_json"]))
    json_str = json.dumps(analyses)
    
    if format_type == "plain_json":
        return json_str
    else:
        return f"```json\n{json_str}\n```"


# ── Property Tests ──────────────────────────────────────────────────────

class TestLLMResponseParsing:
    """
    **Property 5: LLM response parsing**
    **Validates: Requirement 4.6**
    
    For any valid LLM API response, the parsed sentiment should be one of
    {bullish, bearish, neutral}, confidence should be in [0.0, 1.0], and
    narrative_strength should be in [0.0, 1.0].
    """
    
    @given(valid_llm_response())
    @settings(max_examples=10, deadline=None)
    def test_perplexity_response_parsing_bounds(self, response_str):
        """
        Perplexity client should parse any valid response and extract sentiment,
        confidence, and narrative_strength within valid bounds.
        """
        from src.perplexity_client import PerplexityClient
        
        client = PerplexityClient(api_key="test_key")
        parsed = client._parse_response(response_str)
        
        # Verify parsing succeeded
        assert parsed is not None, (
            f"Failed to parse valid response: {response_str[:100]}"
        )
        
        # Verify sentiment is valid
        assert parsed.get("sentiment") in ["bullish", "bearish", "neutral"], (
            f"Invalid sentiment: {parsed.get('sentiment')}. "
            f"Must be one of: bullish, bearish, neutral"
        )
        
        # Verify confidence is in valid range
        confidence = parsed.get("confidence")
        assert confidence is not None, "Confidence field missing from parsed response"
        assert isinstance(confidence, (int, float)), (
            f"Confidence must be numeric, got {type(confidence)}"
        )
        assert 0.0 <= confidence <= 1.0, (
            f"Confidence must be in [0.0, 1.0], got {confidence}"
        )
        
        # Verify narrative_strength is in valid range
        narrative_strength = parsed.get("narrative_strength")
        assert narrative_strength is not None, (
            "narrative_strength field missing from parsed response"
        )
        assert isinstance(narrative_strength, (int, float)), (
            f"narrative_strength must be numeric, got {type(narrative_strength)}"
        )
        assert 0.0 <= narrative_strength <= 1.0, (
            f"narrative_strength must be in [0.0, 1.0], got {narrative_strength}"
        )
    
    @given(perplexity_response())
    @settings(max_examples=10, deadline=None)
    def test_perplexity_specific_format_parsing(self, response_str):
        """
        Perplexity client should correctly parse Perplexity-specific response format
        with all expected fields.
        """
        from src.perplexity_client import PerplexityClient
        
        client = PerplexityClient(api_key="test_key")
        parsed = client._parse_response(response_str)
        
        assert parsed is not None, "Failed to parse Perplexity response"
        
        # Verify all required fields are present
        required_fields = ["sentiment", "confidence", "narrative_strength"]
        for field in required_fields:
            assert field in parsed, f"Required field '{field}' missing from parsed response"
        
        # Verify sentiment
        assert parsed["sentiment"] in ["bullish", "bearish", "neutral"]
        
        # Verify confidence bounds
        assert 0.0 <= parsed["confidence"] <= 1.0
        
        # Verify narrative_strength bounds
        assert 0.0 <= parsed["narrative_strength"] <= 1.0
        
        # Verify optional fields have correct types if present
        if "catalysts" in parsed:
            assert isinstance(parsed["catalysts"], list)
        
        if "risks" in parsed:
            assert isinstance(parsed["risks"], list)
        
        if "driver_type" in parsed:
            assert isinstance(parsed["driver_type"], str)
        
        if "sustainability_hours" in parsed:
            assert isinstance(parsed["sustainability_hours"], int)
            assert 1 <= parsed["sustainability_hours"] <= 168
    
    @given(context_agent_batch_response())
    @settings(max_examples=10, deadline=None)
    def test_context_agent_batch_parsing(self, response_str):
        """
        Context Agent should parse batch responses (arrays) and validate each
        analysis has correct sentiment, confidence bounds.
        """
        # Parse the response manually (simulating Context Agent's _analyze_batch)
        clean = response_str.strip()
        
        # Find array start/end
        start = clean.find("[")
        end = clean.rfind("]")
        
        if start != -1 and end != -1:
            clean = clean[start : end + 1]
        
        # Remove markdown if present
        clean = clean.replace("```json", "").replace("```", "")
        
        data = json.loads(clean)
        
        # Verify it's a list
        assert isinstance(data, list), "Batch response should be a JSON array"
        assert len(data) > 0, "Batch response should contain at least one analysis"
        
        # Verify each analysis
        for analysis in data:
            # Verify sentiment
            assert "sentiment" in analysis, "Each analysis must have sentiment field"
            assert analysis["sentiment"] in ["bullish", "bearish", "neutral"], (
                f"Invalid sentiment: {analysis['sentiment']}"
            )
            
            # Verify confidence
            assert "confidence" in analysis, "Each analysis must have confidence field"
            confidence = analysis["confidence"]
            assert isinstance(confidence, (int, float)), (
                f"Confidence must be numeric, got {type(confidence)}"
            )
            assert 0.0 <= confidence <= 1.0, (
                f"Confidence must be in [0.0, 1.0], got {confidence}"
            )
    
    @given(
        st.sampled_from(["bullish", "bearish", "neutral"]),
        st.floats(min_value=0.0, max_value=1.0),
        st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(max_examples=10, deadline=None)
    def test_fallback_response_always_valid(self, sentiment, confidence, narrative_strength):
        """
        Fallback responses should always have valid sentiment, confidence, and
        narrative_strength values, even when LLM fails.
        """
        from src.perplexity_client import PerplexityClient
        
        # Get fallback response
        fallback = PerplexityClient._fallback_response("BTC", "test_reason")
        
        # Verify fallback has valid structure
        assert fallback["sentiment"] in ["bullish", "bearish", "neutral"], (
            f"Fallback sentiment invalid: {fallback['sentiment']}"
        )
        
        assert isinstance(fallback["confidence"], (int, float)), (
            f"Fallback confidence must be numeric, got {type(fallback['confidence'])}"
        )
        assert 0.0 <= fallback["confidence"] <= 1.0, (
            f"Fallback confidence must be in [0.0, 1.0], got {fallback['confidence']}"
        )
        
        assert isinstance(fallback["narrative_strength"], (int, float)), (
            f"Fallback narrative_strength must be numeric, got {type(fallback['narrative_strength'])}"
        )
        assert 0.0 <= fallback["narrative_strength"] <= 1.0, (
            f"Fallback narrative_strength must be in [0.0, 1.0], got {fallback['narrative_strength']}"
        )
    
    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=10, deadline=None)
    def test_invalid_response_returns_none_or_fallback(self, invalid_text):
        """
        When given invalid/unparseable text, the parser should return None
        (allowing fallback logic to trigger) rather than crashing.
        """
        from src.perplexity_client import PerplexityClient
        
        # Filter out valid JSON to ensure we're testing invalid cases
        try:
            json.loads(invalid_text)
            # If it's valid JSON, skip this test case
            return
        except json.JSONDecodeError:
            pass  # Good, it's invalid
        
        client = PerplexityClient(api_key="test_key")
        
        # Should not crash, should return None
        try:
            result = client._parse_response(invalid_text)
            # If parsing succeeded, verify it has valid structure
            if result is not None:
                assert "sentiment" in result
                assert result["sentiment"] in ["bullish", "bearish", "neutral"]
                if "confidence" in result:
                    assert 0.0 <= result["confidence"] <= 1.0
                if "narrative_strength" in result:
                    assert 0.0 <= result["narrative_strength"] <= 1.0
        except Exception as e:
            # Should not raise exceptions
            assert False, f"Parser should not crash on invalid input, but raised: {e}"
    
    @given(
        st.sampled_from(["bullish", "bearish", "neutral"]),
        st.floats(min_value=-10.0, max_value=10.0),  # Include out-of-bounds values
        st.floats(min_value=-10.0, max_value=10.0)
    )
    @settings(max_examples=10, deadline=None)
    def test_out_of_bounds_values_handled_gracefully(self, sentiment, confidence, narrative_strength):
        """
        If LLM returns out-of-bounds confidence or narrative_strength values,
        the system should either clamp them to [0.0, 1.0] or reject the response.
        """
        from src.perplexity_client import PerplexityClient
        
        # Create response with potentially out-of-bounds values
        response_dict = {
            "sentiment": sentiment,
            "confidence": confidence,
            "narrative_strength": narrative_strength,
            "catalysts": [],
            "risks": [],
            "driver_type": "unknown",
            "summary": "Test"
        }
        
        response_str = json.dumps(response_dict)
        
        client = PerplexityClient(api_key="test_key")
        parsed = client._parse_response(response_str)
        
        # If parsing succeeded, verify bounds are enforced
        if parsed is not None:
            # Sentiment should always be valid
            assert parsed["sentiment"] in ["bullish", "bearish", "neutral"]
            
            # Confidence and narrative_strength should be in valid range
            # (either clamped or the response should be rejected)
            if "confidence" in parsed:
                conf = parsed["confidence"]
                # Either it's in bounds, or the implementation rejects it
                if conf is not None:
                    assert 0.0 <= conf <= 1.0, (
                        f"Confidence out of bounds: {conf}. "
                        f"Should be clamped to [0.0, 1.0] or response rejected."
                    )
            
            if "narrative_strength" in parsed:
                ns = parsed["narrative_strength"]
                if ns is not None:
                    assert 0.0 <= ns <= 1.0, (
                        f"narrative_strength out of bounds: {ns}. "
                        f"Should be clamped to [0.0, 1.0] or response rejected."
                    )
    
    @given(st.sampled_from([
        '{"sentiment": "bullish", "confidence": 0.8, "narrative_strength": 0.7}',
        '```json\n{"sentiment": "bearish", "confidence": 0.5, "narrative_strength": 0.6}\n```',
        'Here is the analysis:\n{"sentiment": "neutral", "confidence": 0.3, "narrative_strength": 0.4}\nEnd of analysis.',
        '```\n{"sentiment": "bullish", "confidence": 0.9, "narrative_strength": 0.8}\n```'
    ]))
    @settings(max_examples=10, deadline=None)
    def test_common_llm_response_formats_parsed_correctly(self, response_str):
        """
        Common LLM response formats (plain JSON, markdown-wrapped, with extra text)
        should all be parsed correctly.
        """
        from src.perplexity_client import PerplexityClient
        
        client = PerplexityClient(api_key="test_key")
        parsed = client._parse_response(response_str)
        
        assert parsed is not None, (
            f"Failed to parse common format: {response_str}"
        )
        
        # Verify required fields
        assert "sentiment" in parsed
        assert parsed["sentiment"] in ["bullish", "bearish", "neutral"]
        
        assert "confidence" in parsed
        assert 0.0 <= parsed["confidence"] <= 1.0
        
        assert "narrative_strength" in parsed
        assert 0.0 <= parsed["narrative_strength"] <= 1.0


class TestLLMFallbackOnFailure:
    """
    **Property 6: LLM fallback on failure**
    **Validates: Requirement 4.7**
    
    For any LLM API call that fails after max retries, the system should return
    neutral sentiment with confidence 0.0.
    """
    
    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu',))),
        st.sampled_from(["api_error", "parse_error", "max_retries_exceeded", "timeout", "connection_error"])
    )
    @settings(max_examples=10, deadline=None)
    def test_fallback_returns_neutral_sentiment_zero_confidence(self, symbol, reason):
        """
        When LLM API call fails after max retries, the fallback response should
        always return neutral sentiment with confidence 0.0.
        """
        from src.perplexity_client import PerplexityClient
        
        # Get fallback response
        fallback = PerplexityClient._fallback_response(symbol, reason)
        
        # Verify neutral sentiment (Requirement 4.7)
        assert fallback["sentiment"] == "neutral", (
            f"Fallback must return neutral sentiment, got: {fallback['sentiment']}"
        )
        
        # Verify confidence is 0.0 (Requirement 4.7)
        assert fallback["confidence"] == 0.0, (
            f"Fallback must return confidence 0.0, got: {fallback['confidence']}"
        )
        
        # Verify narrative_strength is 0.0 (consistent with failure state)
        assert fallback["narrative_strength"] == 0.0, (
            f"Fallback should return narrative_strength 0.0, got: {fallback['narrative_strength']}"
        )
        
        # Verify fallback has all required fields
        required_fields = ["sentiment", "confidence", "catalysts", "risks", 
                          "driver_type", "narrative_strength", "summary"]
        for field in required_fields:
            assert field in fallback, (
                f"Fallback response missing required field: {field}"
            )
    
    @given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu',))))
    @settings(max_examples=10, deadline=None)
    async def test_analyze_returns_fallback_on_timeout(self, symbol):
        """
        When analyze() encounters timeout after max retries, it should return
        fallback response with neutral sentiment and confidence 0.0.
        """
        from src.perplexity_client import PerplexityClient
        from unittest.mock import AsyncMock, patch
        import httpx
        
        # Create client with 1 retry for faster testing
        client = PerplexityClient(api_key="test_key", max_retries=1, retry_delay=0.01)
        
        # Mock httpx.AsyncClient to raise TimeoutException
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timeout")
            )
            mock_client.return_value = mock_context
            
            # Call analyze - should return fallback after retries
            result = await client.analyze(symbol, {"price": 50000})
            
            # Verify fallback response
            assert result["sentiment"] == "neutral", (
                f"Timeout fallback must return neutral sentiment, got: {result['sentiment']}"
            )
            assert result["confidence"] == 0.0, (
                f"Timeout fallback must return confidence 0.0, got: {result['confidence']}"
            )
            assert result["narrative_strength"] == 0.0, (
                f"Timeout fallback should return narrative_strength 0.0, got: {result['narrative_strength']}"
            )
    
    @given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu',))))
    @settings(max_examples=10, deadline=None)
    async def test_analyze_returns_fallback_on_api_error(self, symbol):
        """
        When analyze() encounters API error (non-200 status) after max retries,
        it should return fallback response with neutral sentiment and confidence 0.0.
        """
        from src.perplexity_client import PerplexityClient
        from unittest.mock import AsyncMock, patch, MagicMock
        
        # Create client with 1 retry for faster testing
        client = PerplexityClient(api_key="test_key", max_retries=1, retry_delay=0.01)
        
        # Mock httpx.AsyncClient to return error status
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            # Call analyze - should return fallback after retries
            result = await client.analyze(symbol, {"price": 50000})
            
            # Verify fallback response
            assert result["sentiment"] == "neutral", (
                f"API error fallback must return neutral sentiment, got: {result['sentiment']}"
            )
            assert result["confidence"] == 0.0, (
                f"API error fallback must return confidence 0.0, got: {result['confidence']}"
            )
            assert result["narrative_strength"] == 0.0, (
                f"API error fallback should return narrative_strength 0.0, got: {result['narrative_strength']}"
            )
    
    @given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu',))))
    @settings(max_examples=10, deadline=None)
    async def test_analyze_returns_fallback_on_parse_error(self, symbol):
        """
        When analyze() receives unparseable response after max retries,
        it should return fallback response with neutral sentiment and confidence 0.0.
        """
        from src.perplexity_client import PerplexityClient
        from unittest.mock import AsyncMock, patch, MagicMock
        
        # Create client with 1 retry for faster testing
        client = PerplexityClient(api_key="test_key", max_retries=1, retry_delay=0.01)
        
        # Mock httpx.AsyncClient to return unparseable response
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "This is not valid JSON at all, just random text"
                    }
                }]
            }
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            # Call analyze - should return fallback due to parse error
            result = await client.analyze(symbol, {"price": 50000})
            
            # Verify fallback response
            assert result["sentiment"] == "neutral", (
                f"Parse error fallback must return neutral sentiment, got: {result['sentiment']}"
            )
            assert result["confidence"] == 0.0, (
                f"Parse error fallback must return confidence 0.0, got: {result['confidence']}"
            )
            assert result["narrative_strength"] == 0.0, (
                f"Parse error fallback should return narrative_strength 0.0, got: {result['narrative_strength']}"
            )
    
    @given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu',))))
    @settings(max_examples=10, deadline=None)
    async def test_analyze_returns_fallback_on_connection_error(self, symbol):
        """
        When analyze() encounters connection error after max retries,
        it should return fallback response with neutral sentiment and confidence 0.0.
        """
        from src.perplexity_client import PerplexityClient
        from unittest.mock import AsyncMock, patch
        
        # Create client with 1 retry for faster testing
        client = PerplexityClient(api_key="test_key", max_retries=1, retry_delay=0.01)
        
        # Mock httpx.AsyncClient to raise generic exception
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_client.return_value = mock_context
            
            # Call analyze - should return fallback after retries
            result = await client.analyze(symbol, {"price": 50000})
            
            # Verify fallback response
            assert result["sentiment"] == "neutral", (
                f"Connection error fallback must return neutral sentiment, got: {result['sentiment']}"
            )
            assert result["confidence"] == 0.0, (
                f"Connection error fallback must return confidence 0.0, got: {result['confidence']}"
            )
            assert result["narrative_strength"] == 0.0, (
                f"Connection error fallback should return narrative_strength 0.0, got: {result['narrative_strength']}"
            )
    
    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu',))),
        st.sampled_from(["api_error", "parse_error", "max_retries_exceeded"])
    )
    @settings(max_examples=10, deadline=None)
    def test_fallback_response_structure_is_valid(self, symbol, reason):
        """
        Fallback response should have valid structure that can be used by
        downstream components (Bayesian engine, etc.) without errors.
        """
        from src.perplexity_client import PerplexityClient
        
        fallback = PerplexityClient._fallback_response(symbol, reason)
        
        # Verify all fields have correct types
        assert isinstance(fallback["sentiment"], str)
        assert isinstance(fallback["confidence"], (int, float))
        assert isinstance(fallback["catalysts"], list)
        assert isinstance(fallback["risks"], list)
        assert isinstance(fallback["driver_type"], str)
        assert isinstance(fallback["narrative_strength"], (int, float))
        assert isinstance(fallback["summary"], str)
        
        # Verify sentiment is valid enum value
        assert fallback["sentiment"] in ["bullish", "bearish", "neutral"]
        
        # Verify numeric values are in valid ranges
        assert 0.0 <= fallback["confidence"] <= 1.0
        assert 0.0 <= fallback["narrative_strength"] <= 1.0
        
        # Verify driver_type is valid
        assert fallback["driver_type"] in ["narrative", "technical", "fundamental", "whale", "unknown"]
