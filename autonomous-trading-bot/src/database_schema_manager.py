"""
Database Schema Manager.
Creates and manages Supabase tables for trades, decisions, metrics, and backtest results.
"""
from typing import Dict, Optional
from loguru import logger
from .supabase_client import SupabaseStore


class DatabaseSchemaManager:
    """
    Manages database schema creation and validation for the trading bot.
    
    Creates tables for:
    - trades: Trade execution records
    - decisions: Bayesian decision logs
    - performance_metrics: Daily/weekly performance tracking
    - backtest_results: Historical backtest runs
    - ml_predictions: ML model predictions and outcomes
    - edge_cases: Edge case identification and resolution
    """
    
    def __init__(self, store: Optional[SupabaseStore] = None):
        """
        Initialize schema manager.
        
        Args:
            store: SupabaseStore instance (optional, will create if not provided)
        """
        self.store = store
        logger.info("Database schema manager initialized")
    
    def get_schema_sql(self) -> str:
        """
        Get complete SQL schema for all required tables.
        
        Returns:
            SQL string with CREATE TABLE statements
        """
        return """
-- ===== Core Trading Tables =====

-- Trades table (enhanced for optimization pipeline)
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    notional_usd DECIMAL(20, 2),
    trade_type VARCHAR(30),
    pnl DECIMAL(20, 2),
    r_multiple DECIMAL(10, 2),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    exchange VARCHAR(20) DEFAULT 'gateio',
    entry_price DECIMAL(20, 8),
    exit_price DECIMAL(20, 8),
    entry_time TIMESTAMPTZ,
    exit_time TIMESTAMPTZ,
    setup_type VARCHAR(30),
    status VARCHAR(20) DEFAULT 'open'
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_setup_type ON trades(setup_type);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);

-- Decisions table (Bayesian decision logs)
CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    posterior DECIMAL(10, 4) NOT NULL,
    action VARCHAR(20) NOT NULL,
    setup_type VARCHAR(30),
    mode VARCHAR(20),
    reasoning JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_symbol ON decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_action ON decisions(action);

-- ===== Performance Tracking Tables =====

-- Performance metrics table (daily/weekly tracking)
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    total_trades INTEGER,
    win_rate DECIMAL(10, 4),
    profit_factor DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    total_pnl DECIMAL(20, 2),
    avg_r_multiple DECIMAL(10, 2),
    daily_pnl DECIMAL(20, 2),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_metrics(date DESC);

-- ===== Backtesting Tables =====

-- Backtest results table
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    parameters JSONB NOT NULL,
    metrics JSONB NOT NULL,
    trades_count INTEGER,
    win_rate DECIMAL(10, 4),
    profit_factor DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    total_pnl DECIMAL(20, 2),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_run_id ON backtest_results(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_timestamp ON backtest_results(timestamp DESC);

-- ===== ML Pipeline Tables =====

-- ML predictions table
CREATE TABLE IF NOT EXISTS ml_predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    features JSONB NOT NULL,
    prediction DECIMAL(10, 4),
    confidence DECIMAL(10, 4),
    actual_outcome BOOLEAN,
    model_version VARCHAR(50),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_symbol ON ml_predictions(symbol);
CREATE INDEX IF NOT EXISTS idx_ml_timestamp ON ml_predictions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ml_model_version ON ml_predictions(model_version);

-- ===== Edge Case Tracking =====

-- Edge cases table
CREATE TABLE IF NOT EXISTS edge_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    context JSONB,
    resolution_status VARCHAR(20) DEFAULT 'open',
    resolution_notes TEXT,
    frequency INTEGER DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edge_category ON edge_cases(category);
CREATE INDEX IF NOT EXISTS idx_edge_status ON edge_cases(resolution_status);
CREATE INDEX IF NOT EXISTS idx_edge_timestamp ON edge_cases(timestamp DESC);

-- ===== Existing Tables (from original schema) =====

-- Watcher signals
CREATE TABLE IF NOT EXISTS watcher_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    score DOUBLE PRECISION,
    features JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_watcher_signals_created ON watcher_signals(created_at DESC);

-- Analyzer signals
CREATE TABLE IF NOT EXISTS analyzer_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    setup_type TEXT,
    ta_score DOUBLE PRECISION,
    features JSONB DEFAULT '{}',
    entry_zone JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_analyzer_signals_created ON analyzer_signals(created_at DESC);

-- Context analysis
CREATE TABLE IF NOT EXISTS context_analysis (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    sentiment TEXT,
    confidence DOUBLE PRECISION,
    catalysts JSONB DEFAULT '[]',
    risks JSONB DEFAULT '[]',
    driver_type TEXT,
    narrative_strength DOUBLE PRECISION
);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    side TEXT DEFAULT 'long',
    status TEXT DEFAULT 'open',
    entry_price DOUBLE PRECISION,
    current_price DOUBLE PRECISION,
    quantity DOUBLE PRECISION,
    notional_usd DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION DEFAULT 0,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- BigBrother events
CREATE TABLE IF NOT EXISTS bigbrother_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    event_type TEXT NOT NULL,
    severity TEXT,
    message TEXT,
    details JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_bigbrother_events_created ON bigbrother_events(created_at DESC);

-- User interactions
CREATE TABLE IF NOT EXISTS user_interactions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    interaction_type TEXT,
    content TEXT,
    response TEXT
);
"""
    
    def create_all_tables(self) -> Dict:
        """
        Execute all CREATE TABLE statements.
        
        Returns:
            Dict with status and any errors
        """
        logger.info("Creating all database tables...")
        
        try:
            if self.store is None:
                logger.warning("No SupabaseStore provided, cannot create tables")
                return {"status": "error", "message": "No database connection"}
            
            # Get SQL schema
            schema_sql = self.get_schema_sql()
            
            # Execute via Supabase (note: this requires service role key for DDL)
            # In practice, you'd run this SQL directly in Supabase SQL Editor
            # or use a migration tool
            
            logger.info("Schema SQL generated. Execute in Supabase SQL Editor:")
            logger.info("=" * 80)
            logger.info(schema_sql)
            logger.info("=" * 80)
            
            return {
                "status": "success",
                "message": "Schema SQL generated. Execute in Supabase SQL Editor.",
                "sql": schema_sql
            }
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return {"status": "error", "message": str(e)}
    
    def validate_schema(self) -> Dict:
        """
        Verify all required tables exist.
        
        Returns:
            Dict with validation results
        """
        logger.info("Validating database schema...")
        
        required_tables = [
            "trades",
            "decisions",
            "performance_metrics",
            "backtest_results",
            "ml_predictions",
            "edge_cases",
            "watcher_signals",
            "analyzer_signals",
            "context_analysis",
            "positions",
            "bigbrother_events",
            "user_interactions"
        ]
        
        try:
            if self.store is None:
                return {"status": "error", "message": "No database connection"}
            
            # Check if tables exist by attempting to query them
            missing_tables = []
            existing_tables = []
            
            for table in required_tables:
                try:
                    # Try to query the table (limit 0 to avoid loading data)
                    result = self.store.client.table(table).select("*").limit(0).execute()
                    existing_tables.append(table)
                except Exception as e:
                    logger.warning(f"Table {table} not found or not accessible: {e}")
                    missing_tables.append(table)
            
            if missing_tables:
                logger.warning(f"Missing tables: {missing_tables}")
                return {
                    "status": "incomplete",
                    "existing_tables": existing_tables,
                    "missing_tables": missing_tables
                }
            else:
                logger.info(f"All {len(required_tables)} tables validated successfully")
                return {
                    "status": "success",
                    "existing_tables": existing_tables,
                    "missing_tables": []
                }
                
        except Exception as e:
            logger.error(f"Error validating schema: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_table_list(self) -> list:
        """
        Get list of all tables in the schema.
        
        Returns:
            List of table names
        """
        return [
            "trades",
            "decisions",
            "performance_metrics",
            "backtest_results",
            "ml_predictions",
            "edge_cases",
            "watcher_signals",
            "analyzer_signals",
            "context_analysis",
            "positions",
            "bigbrother_events",
            "user_interactions"
        ]
    
    def save_schema_to_file(self, filepath: str = "schema_complete.sql") -> None:
        """
        Save complete schema SQL to file.
        
        Args:
            filepath: Path to save SQL file
        """
        schema_sql = self.get_schema_sql()
        
        with open(filepath, 'w') as f:
            f.write(schema_sql)
        
        logger.info(f"Schema SQL saved to {filepath}")
