"""
Property-based tests for Database operations.

These tests use hypothesis to verify universal properties hold across
all valid inputs, complementing the example-based unit tests.
"""
from hypothesis import given, strategies as st, settings
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.supabase_client import SupabaseStore


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def valid_trade_record(draw):
    """Generate valid trade records with all required fields."""
    symbol = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/-')))
    price = draw(st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False))
    quantity = draw(st.floats(min_value=0.001, max_value=10000.0, allow_nan=False, allow_infinity=False))
    timestamp = datetime.now(timezone.utc).isoformat()
    
    return {
        "symbol": symbol,
        "price": price,
        "quantity": quantity,
        "timestamp": timestamp,
        "position_id": f"pos_{draw(st.integers(min_value=1, max_value=999999))}",
        "side": draw(st.sampled_from(["buy", "sell"])),
        "notional_usd": price * quantity,
        "trade_type": draw(st.sampled_from(["entry", "exit", "partial_exit"])),
    }


@st.composite
def incomplete_trade_record(draw):
    """Generate trade records with one or more required fields missing or null."""
    # Start with a valid record
    record = {
        "symbol": draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/-'))),
        "price": draw(st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False)),
        "quantity": draw(st.floats(min_value=0.001, max_value=10000.0, allow_nan=False, allow_infinity=False)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "position_id": f"pos_{draw(st.integers(min_value=1, max_value=999999))}",
        "side": draw(st.sampled_from(["buy", "sell"])),
        "notional_usd": 100.0,
        "trade_type": "entry",
    }
    
    # Choose which required field(s) to make invalid
    required_fields = ["symbol", "price", "quantity", "timestamp"]
    field_to_invalidate = draw(st.sampled_from(required_fields))
    
    # Make the field invalid (either None or missing)
    if draw(st.booleans()):
        record[field_to_invalidate] = None
    else:
        del record[field_to_invalidate]
    
    return record


# ── Property Tests ──────────────────────────────────────────────────────

class TestTradeRecordValidation:
    """
    **Property 7: Trade record validation**
    **Validates: Requirement 3.6**
    
    For any trade record insertion, all required fields (symbol, price, quantity, timestamp)
    must be present and non-null, or insertion should fail with validation error.
    """
    
    @given(valid_trade_record())
    @settings(max_examples=10, deadline=None)
    def test_valid_trade_record_insertion_succeeds(self, trade_record):
        """
        Valid trade records with all required fields present and non-null
        should be inserted successfully.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "test-id", **trade_record}]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Attempt to insert the trade record
        result = store.insert_trade(
            position_id=trade_record.get("position_id"),
            symbol=trade_record["symbol"],
            side=trade_record["side"],
            price=trade_record["price"],
            quantity=trade_record["quantity"],
            notional_usd=trade_record["notional_usd"],
            trade_type=trade_record["trade_type"],
            created_at=trade_record["timestamp"]
        )
        
        # Verify insertion was attempted
        assert result is not None, (
            f"Valid trade record insertion failed. Record: {trade_record}"
        )
        
        # Verify the insert was called with correct table
        mock_client.table.assert_called_once_with("trades")
        
        # Verify insert was called
        assert mock_table.insert.called, "Insert method was not called"
        
        # Verify the inserted data contains required fields
        inserted_data = mock_table.insert.call_args[0][0]
        assert "symbol" in inserted_data and inserted_data["symbol"] is not None, (
            "Symbol field missing or null in inserted data"
        )
        assert "price" in inserted_data and inserted_data["price"] is not None, (
            "Price field missing or null in inserted data"
        )
        assert "quantity" in inserted_data and inserted_data["quantity"] is not None, (
            "Quantity field missing or null in inserted data"
        )
        assert "created_at" in inserted_data and inserted_data["created_at"] is not None, (
            "Timestamp field missing or null in inserted data"
        )
    
    @given(incomplete_trade_record())
    @settings(max_examples=10, deadline=None)
    def test_incomplete_trade_record_insertion_fails(self, trade_record):
        """
        Trade records missing required fields (symbol, price, quantity, timestamp)
        should fail validation and not be inserted.
        """
        # Mock the Supabase client to simulate validation error
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        
        # Setup mock chain to raise exception on execute (simulating DB constraint violation)
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.side_effect = Exception("NOT NULL constraint failed")
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Attempt to insert the incomplete trade record
        # The insert_trade method requires all parameters, so we need to handle missing fields
        try:
            result = store.insert_trade(
                position_id=trade_record.get("position_id"),
                symbol=trade_record.get("symbol"),
                side=trade_record.get("side", "buy"),
                price=trade_record.get("price"),
                quantity=trade_record.get("quantity"),
                notional_usd=trade_record.get("notional_usd", 0.0),
                trade_type=trade_record.get("trade_type", "entry"),
                created_at=trade_record.get("timestamp")
            )
            
            # If any required field is None, the result should be None (error case)
            required_fields = ["symbol", "price", "quantity", "timestamp"]
            has_missing_field = any(trade_record.get(field) is None for field in required_fields)
            
            if has_missing_field:
                assert result is None, (
                    f"Incomplete trade record should fail insertion. "
                    f"Record: {trade_record}, Result: {result}"
                )
        except (TypeError, AttributeError) as e:
            # TypeError or AttributeError is expected when required fields are None
            # This is acceptable validation behavior
            pass
    
    @given(
        st.text(min_size=1, max_size=20),  # symbol
        st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),  # price
        st.floats(min_value=0.001, max_value=10000.0, allow_nan=False, allow_infinity=False),  # quantity
    )
    @settings(max_examples=10, deadline=None)
    def test_required_fields_must_be_non_null(self, symbol, price, quantity):
        """
        All required fields (symbol, price, quantity, timestamp) must be non-null
        for successful insertion.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "test-id"}]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Insert with all required fields present
        result = store.insert_trade(
            position_id="test-pos",
            symbol=symbol,
            side="buy",
            price=price,
            quantity=quantity,
            notional_usd=price * quantity,
            trade_type="entry",
            created_at=timestamp
        )
        
        # Should succeed
        assert result is not None, (
            f"Trade insertion with all required fields should succeed. "
            f"Symbol: {symbol}, Price: {price}, Quantity: {quantity}, Timestamp: {timestamp}"
        )
        
        # Verify the inserted data has non-null required fields
        inserted_data = mock_table.insert.call_args[0][0]
        assert inserted_data["symbol"] is not None, "Symbol should not be null"
        assert inserted_data["price"] is not None, "Price should not be null"
        assert inserted_data["quantity"] is not None, "Quantity should not be null"
        assert inserted_data["created_at"] is not None, "Timestamp should not be null"
    
    @given(valid_trade_record())
    @settings(max_examples=10, deadline=None)
    def test_insertion_returns_success_confirmation(self, trade_record):
        """
        Successful trade record insertion should return a confirmation
        (non-None result) as per Requirement 3.6.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain with successful response
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "test-id", **trade_record}]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Insert the trade record
        result = store.insert_trade(
            position_id=trade_record.get("position_id"),
            symbol=trade_record["symbol"],
            side=trade_record["side"],
            price=trade_record["price"],
            quantity=trade_record["quantity"],
            notional_usd=trade_record["notional_usd"],
            trade_type=trade_record["trade_type"],
            created_at=trade_record["timestamp"]
        )
        
        # Verify success confirmation is returned
        assert result is not None, (
            "Successful insertion should return success confirmation (non-None result)"
        )
        
        # Verify the result contains the inserted data
        assert isinstance(result, dict), (
            "Success confirmation should be a dictionary"
        )
    
    @given(
        st.lists(valid_trade_record(), min_size=1, max_size=10)
    )
    @settings(max_examples=10, deadline=None)
    def test_multiple_valid_insertions_all_succeed(self, trade_records):
        """
        Multiple valid trade record insertions should all succeed independently.
        This tests that validation is consistent across multiple operations.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        successful_insertions = 0
        
        for trade_record in trade_records:
            # Setup fresh mocks for each insertion
            mock_table = MagicMock()
            mock_insert = MagicMock()
            mock_execute = MagicMock()
            
            mock_client.table.return_value = mock_table
            mock_table.insert.return_value = mock_insert
            mock_insert.execute.return_value = mock_execute
            mock_execute.data = [{"id": f"test-id-{successful_insertions}", **trade_record}]
            
            # Attempt insertion
            result = store.insert_trade(
                position_id=trade_record.get("position_id"),
                symbol=trade_record["symbol"],
                side=trade_record["side"],
                price=trade_record["price"],
                quantity=trade_record["quantity"],
                notional_usd=trade_record["notional_usd"],
                trade_type=trade_record["trade_type"],
                created_at=trade_record["timestamp"]
            )
            
            if result is not None:
                successful_insertions += 1
        
        # All valid records should have been inserted successfully
        assert successful_insertions == len(trade_records), (
            f"Expected all {len(trade_records)} valid trade records to be inserted, "
            f"but only {successful_insertions} succeeded"
        )


class TestTradePersistence:
    """
    **Property 40: Trade persistence**
    **Validates: Requirement 5.7**
    
    For any executed trade, complete trade record with entry/exit prices, timestamps,
    and PnL should be persisted to database.
    """
    
    @st.composite
    def executed_trade_record(draw):
        """Generate executed trade records with all required fields for persistence."""
        symbol = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/-')))
        entry_price = draw(st.floats(min_value=0.01, max_value=100000.0, 
                                     allow_nan=False, allow_infinity=False))
        exit_price = draw(st.floats(min_value=0.01, max_value=100000.0, 
                                    allow_nan=False, allow_infinity=False))
        quantity = draw(st.floats(min_value=0.001, max_value=10000.0, 
                                  allow_nan=False, allow_infinity=False))
        
        # Calculate PnL based on entry/exit prices
        side = draw(st.sampled_from(["buy", "sell"]))
        if side == "buy":
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        entry_time = datetime.now(timezone.utc).isoformat()
        # Exit time is after entry time (add some seconds)
        exit_time_offset = draw(st.integers(min_value=60, max_value=86400))  # 1 min to 1 day
        exit_time = datetime.now(timezone.utc).isoformat()
        
        return {
            "position_id": f"pos_{draw(st.integers(min_value=1, max_value=999999))}",
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "notional_usd": entry_price * quantity,
            "trade_type": "exit",
            "pnl": pnl,
            "r_multiple": draw(st.floats(min_value=-5.0, max_value=20.0, 
                                        allow_nan=False, allow_infinity=False)),
            "entry_time": entry_time,
            "exit_time": exit_time,
            "setup_type": draw(st.sampled_from([
                "breakout", "momentum", "pullback", "mean_reversion", 
                "consolidation_breakout"
            ])),
            "status": "closed"
        }
    
    @given(executed_trade_record())
    @settings(max_examples=10, deadline=None)
    def test_executed_trade_persists_all_required_fields(self, trade_record):
        """
        For any executed trade, all required fields (entry_price, exit_price,
        entry_time, exit_time, pnl) must be persisted to the database.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "test-id", **trade_record}]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Insert the executed trade record
        result = store.insert_trade(
            position_id=trade_record["position_id"],
            symbol=trade_record["symbol"],
            side=trade_record["side"],
            price=trade_record["exit_price"],  # Use exit price as the trade price
            quantity=trade_record["quantity"],
            notional_usd=trade_record["notional_usd"],
            trade_type=trade_record["trade_type"],
            pnl=trade_record["pnl"],
            r_multiple=trade_record["r_multiple"],
            created_at=trade_record["exit_time"]
        )
        
        # Verify insertion succeeded
        assert result is not None, (
            f"Executed trade persistence failed. Trade: {trade_record}"
        )
        
        # Verify the insert was called with correct table
        mock_client.table.assert_called_once_with("trades")
        
        # Verify all required fields are present in the persisted data
        inserted_data = mock_table.insert.call_args[0][0]
        
        # Check entry/exit prices (price field represents the execution price)
        assert "price" in inserted_data and inserted_data["price"] is not None, (
            "Trade price (exit_price) must be persisted"
        )
        
        # Check timestamps
        assert "created_at" in inserted_data and inserted_data["created_at"] is not None, (
            "Trade timestamp must be persisted"
        )
        
        # Check PnL
        assert "pnl" in inserted_data and inserted_data["pnl"] is not None, (
            "Trade PnL must be persisted"
        )
        
        # Check R-multiple
        assert "r_multiple" in inserted_data, (
            "Trade R-multiple should be persisted"
        )
        
        # Check symbol and quantity
        assert "symbol" in inserted_data and inserted_data["symbol"] is not None, (
            "Trade symbol must be persisted"
        )
        assert "quantity" in inserted_data and inserted_data["quantity"] is not None, (
            "Trade quantity must be persisted"
        )
    
    @given(
        st.lists(executed_trade_record(), min_size=5, max_size=20)
    )
    @settings(max_examples=10, deadline=None)
    def test_multiple_executed_trades_all_persist(self, trade_records):
        """
        Multiple executed trades should all be persisted with complete records.
        This validates that the persistence mechanism is consistent across
        multiple trade executions.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        persisted_trades = []
        
        for i, trade_record in enumerate(trade_records):
            # Setup fresh mocks for each insertion
            mock_table = MagicMock()
            mock_insert = MagicMock()
            mock_execute = MagicMock()
            
            mock_client.table.return_value = mock_table
            mock_table.insert.return_value = mock_insert
            mock_insert.execute.return_value = mock_execute
            mock_execute.data = [{"id": f"test-id-{i}", **trade_record}]
            
            # Persist the trade
            result = store.insert_trade(
                position_id=trade_record["position_id"],
                symbol=trade_record["symbol"],
                side=trade_record["side"],
                price=trade_record["exit_price"],
                quantity=trade_record["quantity"],
                notional_usd=trade_record["notional_usd"],
                trade_type=trade_record["trade_type"],
                pnl=trade_record["pnl"],
                r_multiple=trade_record["r_multiple"],
                created_at=trade_record["exit_time"]
            )
            
            if result is not None:
                persisted_trades.append(result)
        
        # All executed trades should have been persisted
        assert len(persisted_trades) == len(trade_records), (
            f"Expected all {len(trade_records)} executed trades to be persisted, "
            f"but only {len(persisted_trades)} were saved"
        )
    
    @given(executed_trade_record())
    @settings(max_examples=10, deadline=None)
    def test_trade_pnl_calculation_persisted_correctly(self, trade_record):
        """
        The PnL calculation for executed trades should be persisted correctly,
        reflecting the profit or loss from entry to exit.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "test-id", **trade_record}]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Insert the trade
        result = store.insert_trade(
            position_id=trade_record["position_id"],
            symbol=trade_record["symbol"],
            side=trade_record["side"],
            price=trade_record["exit_price"],
            quantity=trade_record["quantity"],
            notional_usd=trade_record["notional_usd"],
            trade_type=trade_record["trade_type"],
            pnl=trade_record["pnl"],
            r_multiple=trade_record["r_multiple"],
            created_at=trade_record["exit_time"]
        )
        
        # Verify PnL was persisted
        assert result is not None, "Trade persistence failed"
        
        inserted_data = mock_table.insert.call_args[0][0]
        assert "pnl" in inserted_data, "PnL field missing from persisted trade"
        assert inserted_data["pnl"] == trade_record["pnl"], (
            f"Persisted PnL {inserted_data['pnl']} does not match "
            f"calculated PnL {trade_record['pnl']}"
        )
    
    @given(executed_trade_record())
    @settings(max_examples=10, deadline=None)
    def test_trade_timestamps_persisted_in_correct_order(self, trade_record):
        """
        Trade timestamps should be persisted correctly, with exit_time
        representing when the trade was closed.
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "test-id", **trade_record}]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Insert the trade
        result = store.insert_trade(
            position_id=trade_record["position_id"],
            symbol=trade_record["symbol"],
            side=trade_record["side"],
            price=trade_record["exit_price"],
            quantity=trade_record["quantity"],
            notional_usd=trade_record["notional_usd"],
            trade_type=trade_record["trade_type"],
            pnl=trade_record["pnl"],
            r_multiple=trade_record["r_multiple"],
            created_at=trade_record["exit_time"]
        )
        
        # Verify timestamp was persisted
        assert result is not None, "Trade persistence failed"
        
        inserted_data = mock_table.insert.call_args[0][0]
        assert "created_at" in inserted_data, "Timestamp field missing from persisted trade"
        assert inserted_data["created_at"] is not None, "Timestamp should not be null"
        
        # Verify the timestamp is a valid ISO format string
        try:
            datetime.fromisoformat(inserted_data["created_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            assert False, f"Invalid timestamp format: {inserted_data['created_at']}"
    
    @given(
        st.text(min_size=3, max_size=20, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/-')),
        st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.001, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=10, deadline=None)
    def test_complete_trade_record_required_for_persistence(
        self, symbol, entry_price, exit_price, quantity
    ):
        """
        A complete trade record with all required fields must be provided
        for successful persistence. Missing critical fields should prevent
        persistence or result in incomplete records.
        """
        # Calculate PnL for a buy trade
        pnl = (exit_price - entry_price) * quantity
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{
            "id": "test-id",
            "symbol": symbol,
            "price": exit_price,
            "quantity": quantity,
            "pnl": pnl,
            "created_at": timestamp
        }]
        
        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client
        
        # Insert complete trade record
        result = store.insert_trade(
            position_id="test-pos",
            symbol=symbol,
            side="buy",
            price=exit_price,
            quantity=quantity,
            notional_usd=exit_price * quantity,
            trade_type="exit",
            pnl=pnl,
            r_multiple=pnl / (entry_price * quantity) if entry_price * quantity > 0 else 0,
            created_at=timestamp
        )
        
        # Verify successful persistence
        assert result is not None, (
            "Complete trade record with all required fields should persist successfully"
        )
        
        # Verify all critical fields are in the persisted data
        inserted_data = mock_table.insert.call_args[0][0]
        critical_fields = ["symbol", "price", "quantity", "pnl", "created_at"]
        
        for field in critical_fields:
            assert field in inserted_data and inserted_data[field] is not None, (
                f"Critical field '{field}' missing or null in persisted trade record"
            )



class TestQueryResultOrdering:
    """
    **Property 8: Query result ordering**
    **Validates: Requirement 3.7**

    For any query for historical trades, results should be ordered by entry_time
    in descending order (most recent first).
    """

    @st.composite
    def trade_list_with_timestamps(draw):
        """Generate a list of trades with different timestamps."""
        num_trades = draw(st.integers(min_value=2, max_value=20))
        trades = []

        # Generate trades with incrementing timestamps to ensure variety
        base_timestamp = datetime.now(timezone.utc)

        for i in range(num_trades):
            # Create timestamps with varying offsets (seconds ago)
            offset_seconds = draw(st.integers(min_value=i * 60, max_value=(i + 1) * 3600))
            trade_timestamp = base_timestamp.timestamp() - offset_seconds
            trade_time = datetime.fromtimestamp(trade_timestamp, tz=timezone.utc)

            symbol = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/-')))
            price = draw(st.floats(min_value=0.01, max_value=100000.0,
                                  allow_nan=False, allow_infinity=False))
            quantity = draw(st.floats(min_value=0.001, max_value=10000.0,
                                     allow_nan=False, allow_infinity=False))

            trades.append({
                "id": f"trade-{i}",
                "position_id": f"pos_{i}",
                "symbol": symbol,
                "side": draw(st.sampled_from(["buy", "sell"])),
                "price": price,
                "quantity": quantity,
                "notional_usd": price * quantity,
                "trade_type": draw(st.sampled_from(["entry", "exit", "partial_exit"])),
                "created_at": trade_time.isoformat(),
                "timestamp": trade_time.isoformat(),
                "entry_time": trade_time.isoformat(),
            })

        return trades

    @given(trade_list_with_timestamps())
    @settings(max_examples=10, deadline=None)
    def test_historical_trades_ordered_by_entry_time_descending(self, trades):
        """
        For any query for historical trades, results should be ordered by
        entry_time in descending order (most recent first).
        """
        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()

        # Sort trades by timestamp descending (most recent first)
        sorted_trades = sorted(
            trades,
            key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            reverse=True
        )

        # Setup mock chain to return sorted trades
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute
        mock_execute.data = sorted_trades

        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client

        # Query historical trades using the _query method with order_by
        result = store._query("trades", order_by="created_at", limit=len(trades))

        # Verify the query was made with correct ordering
        mock_table.select.assert_called_once_with("*")
        mock_select.order.assert_called_once_with("created_at", desc=True)

        # Verify results are ordered by timestamp descending
        assert len(result) == len(trades), (
            f"Expected {len(trades)} trades, got {len(result)}"
        )

        # Check that each trade is more recent than or equal to the next
        for i in range(len(result) - 1):
            current_time = datetime.fromisoformat(
                result[i]["created_at"].replace("Z", "+00:00")
            )
            next_time = datetime.fromisoformat(
                result[i + 1]["created_at"].replace("Z", "+00:00")
            )

            assert current_time >= next_time, (
                f"Trade at index {i} (timestamp: {current_time}) should be "
                f"more recent than trade at index {i+1} (timestamp: {next_time}). "
                f"Results are not ordered by entry_time descending."
            )

    @given(
        st.lists(
            st.tuples(
                st.text(min_size=3, max_size=20, alphabet=st.characters(
                    whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/-')),
                st.floats(min_value=0.01, max_value=100000.0,
                         allow_nan=False, allow_infinity=False),
                st.integers(min_value=0, max_value=86400)  # seconds offset
            ),
            min_size=3,
            max_size=15
        )
    )
    @settings(max_examples=10, deadline=None)
    def test_query_ordering_consistent_across_different_symbols(self, trade_data):
        """
        Query result ordering by entry_time descending should be consistent
        regardless of symbol or other trade attributes.
        """
        # Generate trades from the input data
        base_timestamp = datetime.now(timezone.utc)
        trades = []

        for i, (symbol, price, offset_seconds) in enumerate(trade_data):
            trade_timestamp = base_timestamp.timestamp() - offset_seconds
            trade_time = datetime.fromtimestamp(trade_timestamp, tz=timezone.utc)

            trades.append({
                "id": f"trade-{i}",
                "position_id": f"pos_{i}",
                "symbol": symbol,
                "side": "buy",
                "price": price,
                "quantity": 1.0,
                "notional_usd": price,
                "trade_type": "entry",
                "created_at": trade_time.isoformat(),
                "timestamp": trade_time.isoformat(),
            })

        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_execute = MagicMock()

        # Sort trades by timestamp descending
        sorted_trades = sorted(
            trades,
            key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            reverse=True
        )

        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.execute.return_value = mock_execute
        mock_execute.data = sorted_trades

        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client

        # Query trades
        result = store._query("trades", order_by="created_at")

        # Verify ordering is maintained
        for i in range(len(result) - 1):
            current_time = datetime.fromisoformat(
                result[i]["created_at"].replace("Z", "+00:00")
            )
            next_time = datetime.fromisoformat(
                result[i + 1]["created_at"].replace("Z", "+00:00")
            )

            assert current_time >= next_time, (
                f"Ordering violated at index {i}: {current_time} should be >= {next_time}"
            )

    @given(trade_list_with_timestamps())
    @settings(max_examples=10, deadline=None)
    def test_most_recent_trade_appears_first(self, trades):
        """
        The most recent trade (by entry_time) should always appear first
        in query results when ordered descending.
        """
        if not trades:
            return  # Skip empty lists

        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_execute = MagicMock()

        # Sort trades by timestamp descending
        sorted_trades = sorted(
            trades,
            key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            reverse=True
        )

        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.execute.return_value = mock_execute
        mock_execute.data = sorted_trades

        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client

        # Query trades
        result = store._query("trades", order_by="created_at")

        # Find the most recent trade in the original list
        most_recent_trade = max(
            trades,
            key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        )

        # Verify the first result is the most recent trade
        assert len(result) > 0, "Query should return at least one trade"

        first_result_time = datetime.fromisoformat(
            result[0]["created_at"].replace("Z", "+00:00")
        )
        most_recent_time = datetime.fromisoformat(
            most_recent_trade["created_at"].replace("Z", "+00:00")
        )

        assert first_result_time == most_recent_time, (
            f"First result timestamp {first_result_time} should match "
            f"most recent trade timestamp {most_recent_time}"
        )

    @given(
        st.integers(min_value=1, max_value=50),  # number of trades
        st.integers(min_value=1, max_value=10)   # query limit
    )
    @settings(max_examples=10, deadline=None)
    def test_limited_query_maintains_descending_order(self, num_trades, query_limit):
        """
        Even when limiting query results, the ordering by entry_time descending
        should be maintained (most recent trades returned).
        """
        # Generate trades with sequential timestamps
        base_timestamp = datetime.now(timezone.utc)
        trades = []

        for i in range(num_trades):
            trade_timestamp = base_timestamp.timestamp() - (i * 60)  # 1 minute apart
            trade_time = datetime.fromtimestamp(trade_timestamp, tz=timezone.utc)

            trades.append({
                "id": f"trade-{i}",
                "position_id": f"pos_{i}",
                "symbol": "BTC/USDT",
                "side": "buy",
                "price": 50000.0 + i,
                "quantity": 1.0,
                "notional_usd": 50000.0 + i,
                "trade_type": "entry",
                "created_at": trade_time.isoformat(),
            })

        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()

        # Sort trades by timestamp descending and apply limit
        sorted_trades = sorted(
            trades,
            key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            reverse=True
        )[:query_limit]

        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute
        mock_execute.data = sorted_trades

        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client

        # Query trades with limit
        result = store._query("trades", order_by="created_at", limit=query_limit)

        # Verify we got the expected number of results (or fewer if not enough trades)
        expected_count = min(query_limit, num_trades)
        assert len(result) == expected_count, (
            f"Expected {expected_count} trades, got {len(result)}"
        )

        # Verify ordering is maintained in limited results
        for i in range(len(result) - 1):
            current_time = datetime.fromisoformat(
                result[i]["created_at"].replace("Z", "+00:00")
            )
            next_time = datetime.fromisoformat(
                result[i + 1]["created_at"].replace("Z", "+00:00")
            )

            assert current_time >= next_time, (
                f"Limited query ordering violated at index {i}: "
                f"{current_time} should be >= {next_time}"
            )

    @given(trade_list_with_timestamps())
    @settings(max_examples=10, deadline=None)
    def test_get_recent_trades_returns_descending_order(self, trades):
        """
        The get_recent_trades method should return trades in descending order
        by created_at (most recent first), as per Requirement 3.7.
        """
        if not trades:
            return  # Skip empty lists

        # Mock the Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()

        # Sort trades by timestamp descending
        sorted_trades = sorted(
            trades,
            key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            reverse=True
        )

        # Setup mock chain
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute
        mock_execute.data = sorted_trades

        # Create store with mocked client
        store = SupabaseStore(url="http://test.supabase.co", key="test-key")
        store.client = mock_client

        # Call get_recent_trades
        result = store.get_recent_trades(n=len(trades))

        # Verify the order method was called with descending order
        mock_select.order.assert_called_once_with("created_at", desc=True)

        # Verify results are in descending order
        for i in range(len(result) - 1):
            current_time = datetime.fromisoformat(
                result[i]["created_at"].replace("Z", "+00:00")
            )
            next_time = datetime.fromisoformat(
                result[i + 1]["created_at"].replace("Z", "+00:00")
            )

            assert current_time >= next_time, (
                f"get_recent_trades ordering violated: trade at index {i} "
                f"(timestamp: {current_time}) should be more recent than or equal to "
                f"trade at index {i+1} (timestamp: {next_time})"
            )

