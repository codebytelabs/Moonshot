#!/usr/bin/env python3
"""
Quick Validation Test (2-Day Demo)

This script runs a shortened 2-day validation for testing purposes.
Use this to verify the validation system is working correctly before
committing to the full 28-day validation.

**Note:** This is for testing only. The full 28-day validation is required
for proper validation before live deployment.

Usage:
    python run_quick_validation.py
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from run_extended_validation import ExtendedValidationRunner
from loguru import logger


async def main():
    """Run quick 2-day validation test."""
    logger.info("="*80)
    logger.info("QUICK VALIDATION TEST (2 DAYS)")
    logger.info("="*80)
    logger.info("This is a shortened validation for testing purposes.")
    logger.info("For proper validation, run the full 28-day validation.")
    logger.info("="*80)
    
    # Create runner with 2-day duration
    runner = ExtendedValidationRunner(
        config_path="optimized_config.json",
        duration_days=2
    )
    
    try:
        await runner.run_validation()
        
        print("\n" + "="*80)
        print("QUICK VALIDATION COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("  1. Review the validation report in validation_reports/")
        print("  2. Check that all systems are working correctly")
        print("  3. If everything looks good, run the full 28-day validation:")
        print("     python run_extended_validation.py")
        print("="*80)
        
        return 0
    
    except Exception as e:
        logger.error(f"Quick validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
