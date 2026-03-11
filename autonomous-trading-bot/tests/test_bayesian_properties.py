"""
Property-based tests for Bayesian Decision Engine.

These tests use hypothesis to verify universal properties hold across
all valid inputs, complementing the example-based unit tests.
"""
from hypothesis import given, strategies as st, settings
from unittest.mock import MagicMock

from src.bayesian_engine import BayesianDecisionEngine, SETUP_PRIORS


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def valid_trade_setup(draw):
    """Generate valid trade setups with non-zero TA score, volume spike, and sentiment."""
    setup_type = draw(st.sampled_from(list(SETUP_PRIORS.keys())))
    ta_score = draw(st.floats(min_value=1.0, max_value=100.0))
    volume_spike = draw(st.floats(min_value=0.1, max_value=10.0))
    sentiment = draw(st.sampled_from(["bullish", "bearish", "neutral"]))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    narrative_strength = draw(st.floats(min_value=0.0, max_value=1.0))
    r_ratio = draw(st.floats(min_value=0.5, max_value=10.0))
    
    # Generate risk count (0-5 risks)
    risk_count = draw(st.integers(min_value=0, max_value=5))
    risks = [f"risk_{i}" for i in range(risk_count)]
    
    return {
        "symbol": "TEST/USDT",
        "ta_score": ta_score,
        "setup_type": setup_type,
        "features": {
            "volume_spike": volume_spike,
            "15m_volume_spike": volume_spike,
        },
        "entry_zone": {
            "entry": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "r_ratio": r_ratio,
        },
        "context": {
            "sentiment": sentiment,
            "confidence": confidence,
            "narrative_strength": narrative_strength,
            "risks": risks,
        },
    }


@st.composite
def high_quality_setup(draw):
    """Generate high-quality setups: TA>70, positive sentiment, volume confirmation."""
    setup_type = draw(st.sampled_from(["breakout", "momentum", "pullback", "consolidation_breakout"]))
    ta_score = draw(st.floats(min_value=70.0, max_value=100.0))
    volume_spike = draw(st.floats(min_value=1.5, max_value=10.0))
    confidence = draw(st.floats(min_value=0.6, max_value=1.0))
    narrative_strength = draw(st.floats(min_value=0.5, max_value=1.0))
    r_ratio = draw(st.floats(min_value=2.0, max_value=10.0))
    
    return {
        "symbol": "TEST/USDT",
        "ta_score": ta_score,
        "setup_type": setup_type,
        "features": {
            "volume_spike": volume_spike,
            "15m_volume_spike": volume_spike,
        },
        "entry_zone": {
            "entry": 100.0,
            "stop_loss": 95.0,
            "take_profit": 120.0,
            "r_ratio": r_ratio,
        },
        "context": {
            "sentiment": "bullish",
            "confidence": confidence,
            "narrative_strength": narrative_strength,
            "risks": [],
        },
    }


# ── Property Tests ──────────────────────────────────────────────────────

class TestBayesianPosteriorBounds:
    """
    **Property 1: Posterior probability bounds**
    **Validates: Requirements 1.1, 1.2, 1.4**
    
    For any valid trade setup with non-zero TA score, volume spike, and sentiment,
    the calculated posterior probability should be in the range [0.0, 1.0] and
    non-zero for setups with TA score >60.
    """
    
    @given(valid_trade_setup())
    @settings(max_examples=10, deadline=None)
    def test_posterior_in_valid_range(self, setup):
        """Posterior probability must be in [0.0, 1.0] for all valid setups."""
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        posterior = result["posterior"]
        assert 0.0 <= posterior <= 1.0, (
            f"Posterior {posterior} out of range [0.0, 1.0] for setup: "
            f"ta_score={setup['ta_score']}, sentiment={setup['context']['sentiment']}, "
            f"volume_spike={setup['features']['volume_spike']}"
        )
    
    @given(valid_trade_setup())
    @settings(max_examples=10, deadline=None)
    def test_posterior_non_zero_for_valid_setups(self, setup):
        """Valid setups with TA>60 should produce non-zero posterior (Requirement 1.1)."""
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        posterior = result["posterior"]
        ta_score = setup["ta_score"]
        risks = setup.get("context", {}).get("risks", [])
        
        # For TA scores >60 with no risks or minimal risks, posterior should be non-zero
        # Setups with 3+ risks may legitimately have zero posterior due to risk penalty
        if ta_score > 60 and len(risks) < 3:
            assert posterior > 0.0, (
                f"Posterior is zero for valid setup with TA score {ta_score} and {len(risks)} risks. "
                f"Setup: sentiment={setup['context']['sentiment']}, "
                f"volume_spike={setup['features']['volume_spike']}, "
                f"r_ratio={setup['entry_zone']['r_ratio']}"
            )
    
    @given(high_quality_setup())
    @settings(max_examples=10, deadline=None)
    def test_high_quality_setup_posterior_threshold(self, setup):
        """
        High-quality setups (TA>70, positive sentiment, volume confirmation)
        should produce posterior >0.50 (Requirement 1.2).
        """
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        posterior = result["posterior"]
        
        assert posterior > 0.50, (
            f"Posterior {posterior} <= 0.50 for high-quality setup: "
            f"ta_score={setup['ta_score']}, sentiment={setup['context']['sentiment']}, "
            f"volume_spike={setup['features']['volume_spike']}, "
            f"confidence={setup['context']['confidence']}, "
            f"narrative_strength={setup['context']['narrative_strength']}"
        )
    
    @given(valid_trade_setup())
    @settings(max_examples=10, deadline=None)
    def test_posterior_normalized_to_unit_range(self, setup):
        """
        Posterior values must be normalized to [0.0, 1.0] range (Requirement 1.4).
        This test verifies the normalization is working correctly.
        """
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        posterior = result["posterior"]
        
        # Verify normalization keeps values in valid probability range
        assert 0.0 <= posterior <= 1.0, (
            f"Normalization failed: posterior {posterior} outside [0.0, 1.0]"
        )
        
        # Verify posterior doesn't exceed 0.99 (as per implementation)
        assert posterior <= 0.99, (
            f"Posterior {posterior} exceeds maximum normalized value of 0.99"
        )
    
    @given(
        st.sampled_from(["normal", "volatile", "safety"]),
        valid_trade_setup()
    )
    @settings(max_examples=10, deadline=None)
    def test_posterior_consistent_across_modes(self, mode, setup):
        """
        Posterior calculation should be consistent regardless of mode.
        Mode only affects the decision threshold, not the posterior value.
        """
        engine_normal = BayesianDecisionEngine(store=None, mode="normal")
        engine_mode = BayesianDecisionEngine(store=None, mode=mode)
        
        result_normal = engine_normal.decide(setup)
        result_mode = engine_mode.decide(setup)
        
        # Posterior should be the same regardless of mode
        assert result_normal["posterior"] == result_mode["posterior"], (
            f"Posterior differs between modes: "
            f"normal={result_normal['posterior']}, {mode}={result_mode['posterior']}"
        )


class TestRiskPenaltyCap:
    """
    **Property 2: Risk penalty cap**
    **Validates: Requirement 1.3**
    
    For any trade setup regardless of risk count, the risk penalty applied to
    posterior probability should never exceed 0.30.
    """
    
    @given(
        st.integers(min_value=0, max_value=20),  # Test with 0-20 risks
        valid_trade_setup()
    )
    @settings(max_examples=10, deadline=None)
    def test_risk_penalty_never_exceeds_cap(self, risk_count, setup):
        """
        Risk penalty must never exceed 0.30 regardless of how many risks are present.
        This ensures the bot doesn't become overly conservative with multiple risks.
        """
        # Override the setup's risks with our test risk count
        setup["context"]["risks"] = [f"risk_{i}" for i in range(risk_count)]
        
        engine = BayesianDecisionEngine(store=None, mode="normal")
        
        # Calculate posterior with risks
        result_with_risks = engine.decide(setup)
        posterior_with_risks = result_with_risks["posterior"]
        
        # Calculate posterior without risks (baseline)
        setup_no_risks = setup.copy()
        setup_no_risks["context"] = setup["context"].copy()
        setup_no_risks["context"]["risks"] = []
        result_no_risks = engine.decide(setup_no_risks)
        posterior_no_risks = result_no_risks["posterior"]
        
        # Calculate actual penalty applied
        actual_penalty = posterior_no_risks - posterior_with_risks
        
        # Penalty should never exceed 0.30
        # Allow small floating point tolerance
        assert actual_penalty <= 0.30 + 0.0001, (
            f"Risk penalty {actual_penalty:.4f} exceeds maximum of 0.30 "
            f"with {risk_count} risks. "
            f"Posterior without risks: {posterior_no_risks:.4f}, "
            f"Posterior with risks: {posterior_with_risks:.4f}"
        )
        
        # Penalty should be non-negative
        assert actual_penalty >= 0.0, (
            f"Risk penalty {actual_penalty:.4f} is negative, which should not happen"
        )
    
    @given(valid_trade_setup())
    @settings(max_examples=10, deadline=None)
    def test_risk_penalty_increases_with_risk_count(self, setup):
        """
        Risk penalty should increase as risk count increases, but cap at 0.30.
        """
        engine = BayesianDecisionEngine(store=None, mode="normal")
        
        # Test with 0, 1, 2, 3, 5, 10 risks
        risk_counts = [0, 1, 2, 3, 5, 10]
        posteriors = []
        
        for risk_count in risk_counts:
            test_setup = setup.copy()
            test_setup["context"] = setup["context"].copy()
            test_setup["context"]["risks"] = [f"risk_{i}" for i in range(risk_count)]
            
            result = engine.decide(test_setup)
            posteriors.append(result["posterior"])
        
        # Posterior should decrease (or stay same) as risks increase
        for i in range(len(posteriors) - 1):
            assert posteriors[i] >= posteriors[i + 1], (
                f"Posterior increased with more risks: "
                f"{risk_counts[i]} risks -> {posteriors[i]:.4f}, "
                f"{risk_counts[i+1]} risks -> {posteriors[i+1]:.4f}"
            )
        
        # Maximum penalty (difference between 0 risks and many risks) should be ≤0.30
        max_penalty = posteriors[0] - posteriors[-1]
        # Allow small floating point tolerance
        assert max_penalty <= 0.30 + 0.0001, (
            f"Maximum penalty {max_penalty:.4f} exceeds cap of 0.30 "
            f"(0 risks: {posteriors[0]:.4f}, {risk_counts[-1]} risks: {posteriors[-1]:.4f})"
        )
    
    @given(
        st.integers(min_value=3, max_value=15),
        high_quality_setup()
    )
    @settings(max_examples=10, deadline=None)
    def test_high_quality_setup_remains_viable_with_risks(self, risk_count, setup):
        """
        Even with many risks, high-quality setups should still produce reasonable
        posteriors due to the 0.30 penalty cap. This prevents the bot from becoming
        too conservative and missing good opportunities.
        """
        # Add many risks to a high-quality setup
        setup["context"]["risks"] = [f"risk_{i}" for i in range(risk_count)]
        
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        posterior = result["posterior"]
        
        # Even with many risks, a high-quality setup should produce a non-trivial posterior
        # The penalty cap ensures we don't go below (original_posterior - 0.30)
        assert posterior >= 0.0, (
            f"Posterior {posterior:.4f} is negative with {risk_count} risks, "
            f"which should not happen"
        )
        
        # Calculate what the posterior would be without risks to verify the cap
        setup_no_risks = setup.copy()
        setup_no_risks["context"] = setup["context"].copy()
        setup_no_risks["context"]["risks"] = []
        result_no_risks = engine.decide(setup_no_risks)
        posterior_no_risks = result_no_risks["posterior"]
        
        # The penalty should not reduce posterior below (original - 0.30)
        expected_minimum = max(0.0, posterior_no_risks - 0.30)
        assert posterior >= expected_minimum - 0.01, (  # Allow small floating point tolerance
            f"Posterior {posterior:.4f} is below expected minimum {expected_minimum:.4f} "
            f"with {risk_count} risks. Original posterior: {posterior_no_risks:.4f}, "
            f"penalty should be capped at 0.30"
        )



class TestLikelihoodMultiplication:
    """
    **Property 3: Likelihood multiplication**
    **Validates: Requirement 1.6**
    
    For any trade setup, the combined likelihood should equal the product of
    TA likelihood, context likelihood, volume likelihood, and R:R factor.
    """
    
    @given(valid_trade_setup())
    @settings(max_examples=10, deadline=None)
    def test_combined_likelihood_is_product_of_components(self, setup):
        """
        The combined likelihood used in posterior calculation must be the exact
        product of all individual likelihood components: TA, context, volume, and R:R.
        """
        from src.bayesian_engine import _sigmoid, _sentiment_likelihood
        
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        # Extract the reasoning which contains individual likelihood components
        reasoning = result["reasoning"]
        ta_likelihood = reasoning["ta_likelihood"]
        context_likelihood = reasoning["context_likelihood"]
        vol_likelihood = reasoning["vol_likelihood"]
        rr_factor = reasoning["rr_factor"]
        
        # Calculate expected combined likelihood
        expected_combined = ta_likelihood * context_likelihood * vol_likelihood * rr_factor
        
        # Calculate what the posterior should be before normalization and risk penalty
        prior = engine.priors.get(setup.get("setup_type", "neutral"), 0.25)
        expected_posterior_before_norm = prior * expected_combined
        
        # Apply normalization (factor of 6.5 as per implementation)
        expected_posterior_normalized = min(0.99, expected_posterior_before_norm * 6.5)
        
        # Apply risk penalty
        risks = setup.get("context", {}).get("risks", [])
        n_risks = len(risks)
        if n_risks == 0:
            expected_penalty = 0.0
        elif n_risks == 1:
            expected_penalty = 0.05
        elif n_risks == 2:
            expected_penalty = 0.10
        else:
            expected_penalty = min(0.30, n_risks * 0.06)
        
        expected_posterior_final = max(0.0, expected_posterior_normalized - expected_penalty)
        
        # The actual posterior should match our calculation
        actual_posterior = result["posterior"]
        
        # Allow small floating point tolerance (0.001)
        assert abs(actual_posterior - expected_posterior_final) < 0.001, (
            f"Posterior calculation doesn't match expected likelihood multiplication. "
            f"Expected: {expected_posterior_final:.4f}, Actual: {actual_posterior:.4f}. "
            f"Components: TA={ta_likelihood:.4f}, Context={context_likelihood:.4f}, "
            f"Volume={vol_likelihood:.4f}, R:R={rr_factor:.4f}, "
            f"Combined={expected_combined:.4f}, Prior={prior:.4f}, "
            f"Before norm={expected_posterior_before_norm:.4f}, "
            f"After norm={expected_posterior_normalized:.4f}, "
            f"Penalty={expected_penalty:.4f}"
        )
    
    @given(valid_trade_setup())
    @settings(max_examples=10, deadline=None)
    def test_likelihood_components_are_probabilities(self, setup):
        """
        All individual likelihood components (TA, context, volume, R:R factor)
        should be valid probabilities in the range [0.0, 1.0].
        """
        engine = BayesianDecisionEngine(store=None, mode="normal")
        result = engine.decide(setup)
        
        reasoning = result["reasoning"]
        ta_likelihood = reasoning["ta_likelihood"]
        context_likelihood = reasoning["context_likelihood"]
        vol_likelihood = reasoning["vol_likelihood"]
        rr_factor = reasoning["rr_factor"]
        
        # All components must be valid probabilities
        assert 0.0 <= ta_likelihood <= 1.0, (
            f"TA likelihood {ta_likelihood} out of range [0.0, 1.0]"
        )
        assert 0.0 <= context_likelihood <= 1.0, (
            f"Context likelihood {context_likelihood} out of range [0.0, 1.0]"
        )
        assert 0.0 <= vol_likelihood <= 1.0, (
            f"Volume likelihood {vol_likelihood} out of range [0.0, 1.0]"
        )
        assert 0.0 <= rr_factor <= 1.0, (
            f"R:R factor {rr_factor} out of range [0.0, 1.0]"
        )
    
    @given(
        st.floats(min_value=1.0, max_value=100.0),  # TA score
        st.sampled_from(["bullish", "bearish", "neutral"]),  # sentiment
        st.floats(min_value=0.1, max_value=10.0),  # volume spike
        st.floats(min_value=0.5, max_value=10.0),  # R:R ratio
    )
    @settings(max_examples=10, deadline=None)
    def test_combined_likelihood_monotonicity(self, ta_score, sentiment, volume_spike, r_ratio):
        """
        Combined likelihood should increase (or stay same) when any individual
        component improves, holding others constant.
        """
        # Create a base setup
        base_setup = {
            "symbol": "TEST/USDT",
            "ta_score": ta_score,
            "setup_type": "breakout",
            "features": {
                "volume_spike": volume_spike,
                "15m_volume_spike": volume_spike,
            },
            "entry_zone": {
                "entry": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "r_ratio": r_ratio,
            },
            "context": {
                "sentiment": sentiment,
                "confidence": 0.7,
                "narrative_strength": 0.6,
                "risks": [],
            },
        }
        
        engine = BayesianDecisionEngine(store=None, mode="normal")
        base_result = engine.decide(base_setup)
        base_posterior = base_result["posterior"]
        
        # Test 1: Improve TA score
        improved_ta_setup = base_setup.copy()
        improved_ta_setup["ta_score"] = min(100.0, ta_score + 10.0)
        improved_ta_result = engine.decide(improved_ta_setup)
        
        # Higher TA score should not decrease posterior (monotonicity)
        assert improved_ta_result["posterior"] >= base_posterior - 0.001, (
            f"Posterior decreased when TA score improved: "
            f"base={base_posterior:.4f} (TA={ta_score:.1f}), "
            f"improved={improved_ta_result['posterior']:.4f} (TA={improved_ta_setup['ta_score']:.1f})"
        )
        
        # Test 2: Improve volume spike
        improved_vol_setup = base_setup.copy()
        improved_vol_setup["features"] = {
            "volume_spike": min(10.0, volume_spike + 1.0),
            "15m_volume_spike": min(10.0, volume_spike + 1.0),
        }
        improved_vol_result = engine.decide(improved_vol_setup)
        
        # Higher volume spike should not decrease posterior
        assert improved_vol_result["posterior"] >= base_posterior - 0.001, (
            f"Posterior decreased when volume spike improved: "
            f"base={base_posterior:.4f} (vol={volume_spike:.2f}), "
            f"improved={improved_vol_result['posterior']:.4f} (vol={improved_vol_setup['features']['volume_spike']:.2f})"
        )
        
        # Test 3: Improve R:R ratio
        improved_rr_setup = base_setup.copy()
        improved_rr_setup["entry_zone"] = base_setup["entry_zone"].copy()
        improved_rr_setup["entry_zone"]["r_ratio"] = min(10.0, r_ratio + 1.0)
        improved_rr_result = engine.decide(improved_rr_setup)
        
        # Higher R:R ratio should not decrease posterior
        assert improved_rr_result["posterior"] >= base_posterior - 0.001, (
            f"Posterior decreased when R:R ratio improved: "
            f"base={base_posterior:.4f} (R:R={r_ratio:.2f}), "
            f"improved={improved_rr_result['posterior']:.4f} (R:R={improved_rr_setup['entry_zone']['r_ratio']:.2f})"
        )
    
    @given(high_quality_setup())
    @settings(max_examples=10, deadline=None)
    def test_zero_component_produces_lower_posterior(self, setup):
        """
        If any likelihood component is reduced to zero or near-zero, the combined
        likelihood should decrease significantly (since it's a product), resulting
        in a lower posterior. We use high-quality setups to ensure the baseline
        posterior is non-zero.
        """
        engine = BayesianDecisionEngine(store=None, mode="normal")
        
        # Get baseline posterior with normal setup
        normal_result = engine.decide(setup)
        baseline_posterior = normal_result["posterior"]
        
        # Baseline should be non-zero for high-quality setup
        assert baseline_posterior > 0.0, (
            f"Baseline posterior should be non-zero for high-quality setup"
        )
        
        # Test with zero TA score (should produce very low TA likelihood)
        zero_ta_setup = setup.copy()
        zero_ta_setup["ta_score"] = 0.0
        result_zero_ta = engine.decide(zero_ta_setup)
        
        # With TA score of 0, the posterior should be much lower than baseline
        assert result_zero_ta["posterior"] < baseline_posterior * 0.5, (
            f"Posterior with zero TA ({result_zero_ta['posterior']:.4f}) "
            f"should be much less than baseline ({baseline_posterior:.4f}). "
            f"Expected at least 50% reduction due to near-zero TA likelihood."
        )
        
        # Test with zero volume spike (should produce low volume likelihood)
        zero_vol_setup = setup.copy()
        zero_vol_setup["features"] = {
            "volume_spike": 0.0,
            "15m_volume_spike": 0.0,
        }
        result_zero_vol = engine.decide(zero_vol_setup)
        
        # With zero volume spike, posterior should be lower than baseline
        assert result_zero_vol["posterior"] < baseline_posterior, (
            f"Posterior with zero volume ({result_zero_vol['posterior']:.4f}) "
            f"should be less than baseline ({baseline_posterior:.4f})"
        )
