"""
Unit tests for Position Manager — Position lifecycle and PnL.
"""
from src.position_manager import Position, PositionState


class TestPosition:
    def test_create_position(self):
        """Position initializes with correct state."""
        pos = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=50000.0,
            quantity=0.1,
            stop_loss=48000.0,
            take_profit=55000.0,
            setup_type="breakout",
            posterior=0.72,
        )
        assert pos.symbol == "BTC/USDT"
        assert pos.status == PositionState.OPEN
        assert pos.entry_price == 50000.0
        assert pos.quantity == 0.1
        assert pos.remaining_quantity == 0.1
        assert pos.tiers_exited == 0

    def test_r_multiple_positive(self):
        """Price above entry → positive R-multiple."""
        pos = Position("ETH/USDT", "long", 3000, 1.0, 2800, 3500, "momentum", 0.7)
        pos.current_price = 3400
        r = pos.r_multiple
        # R = (3400 - 3000) / (3000 - 2800) = 400/200 = 2.0
        assert abs(r - 2.0) < 0.01

    def test_r_multiple_negative(self):
        """Price below entry → negative R-multiple."""
        pos = Position("ETH/USDT", "long", 3000, 1.0, 2800, 3500, "momentum", 0.7)
        pos.current_price = 2900
        r = pos.r_multiple
        # R = (2900 - 3000) / (3000 - 2800) = -100/200 = -0.5
        assert abs(r - (-0.5)) < 0.01

    def test_notional_usd(self):
        """Notional USD = remaining_qty * current_price."""
        pos = Position("SOL/USDT", "long", 100.0, 10.0, 90.0, 120.0, "pullback", 0.6)
        pos.current_price = 110.0
        assert pos.notional_usd == 10.0 * 110.0

    def test_unrealized_pnl(self):
        """Unrealized PnL calculation."""
        pos = Position("SOL/USDT", "long", 100.0, 10.0, 90.0, 120.0, "pullback", 0.6)
        pos.current_price = 105.0
        # PnL = (105 - 100) * 10 = 50
        assert pos.unrealized_pnl == 50.0

    def test_closed_state(self):
        """After setting status to CLOSED, position reflects it."""
        pos = Position("BTC/USDT", "long", 50000, 0.1, 48000, 55000, "breakout", 0.7)
        pos.status = PositionState.CLOSED
        assert pos.status == "closed"

    def test_highest_price_tracking(self):
        """Highest price updates correctly."""
        pos = Position("BTC/USDT", "long", 50000, 0.1, 48000, 55000, "breakout", 0.7)
        assert pos.highest_price == 50000
        pos.current_price = 52000
        pos.highest_price = max(pos.highest_price, pos.current_price)
        assert pos.highest_price == 52000

    def test_to_dict(self):
        """Position should serialize to dict."""
        pos = Position("BTC/USDT", "long", 50000, 0.1, 48000, 55000, "breakout", 0.7)
        d = pos.to_dict()
        assert isinstance(d, dict)
        assert d["symbol"] == "BTC/USDT"
        assert d["entry_price"] == 50000
        assert "status" in d
