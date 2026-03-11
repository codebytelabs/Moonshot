-- Add exchange_trade_id to trades table to track external IDs
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exchange_trade_id TEXT;

-- Create a unique index to prevent duplicate trades from the same exchange
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_exchange_id ON trades(exchange, exchange_trade_id);
