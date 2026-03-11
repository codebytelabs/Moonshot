-- Migration: Add validation_reports table
-- Purpose: Store comprehensive validation reports from extended demo trading
-- Requirements: 24.8

CREATE TABLE IF NOT EXISTS validation_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    duration_days INTEGER NOT NULL,
    
    -- Metrics
    demo_metrics JSONB NOT NULL,
    backtest_metrics JSONB NOT NULL,
    performance_comparison JSONB NOT NULL,
    variance_analysis JSONB NOT NULL,
    edge_case_summary JSONB NOT NULL,
    
    -- Recommendation
    go_no_go VARCHAR(20) NOT NULL CHECK (go_no_go IN ('GO', 'NO_GO', 'CONDITIONAL')),
    recommendation_notes TEXT NOT NULL,
    risk_assessment JSONB NOT NULL,
    
    -- Chart paths
    equity_curve_chart_path TEXT,
    performance_comparison_chart_path TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_validation_reports_created_at (created_at DESC),
    INDEX idx_validation_reports_go_no_go (go_no_go)
);

-- Add comment
COMMENT ON TABLE validation_reports IS 'Comprehensive validation reports from 28-day extended demo trading';
COMMENT ON COLUMN validation_reports.go_no_go IS 'Recommendation: GO, NO_GO, or CONDITIONAL';
COMMENT ON COLUMN validation_reports.demo_metrics IS 'Performance metrics from demo trading period';
COMMENT ON COLUMN validation_reports.backtest_metrics IS 'Expected metrics from backtest for comparison';
COMMENT ON COLUMN validation_reports.variance_analysis IS 'Variance analysis between backtest and demo';
