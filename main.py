#!/usr/bin/env python3
"""
Shopify Product Uploader - CLI Entry Point

Version 2.6.0 - Refactored Modular Structure
Shopify GraphQL Admin API 2025-10

Command-line interface for uploading products to Shopify.
For GUI interface, use gui.py instead.
"""

import argparse
import sys
import os
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from uploader_modules.config import load_config, save_config, SCRIPT_VERSION
from uploader_modules.product_processing import process_products


def setup_logging(log_file: str, verbose: bool = False) -> None:
    """Configure logging for CLI mode."""
    log_level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers
    )


def print_status(message: str) -> None:
    """Status callback for CLI mode - prints to stdout."""
    print(message)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Shopify Product Uploader - Upload products to Shopify via GraphQL API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input products.json --output results.json
  %(prog)s --input products.json --output results.json --mode overwrite
  %(prog)s --input products.json --output results.json --verbose
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input JSON file containing product data"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path to output JSON file for results"
    )
    parser.add_argument(
        "--collections-output", "-c",
        help="Path to collections output JSON file (default: collections.json)"
    )
    parser.add_argument(
        "--log", "-l",
        help="Path to log file (optional)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["resume", "overwrite"],
        default="resume",
        help="Execution mode: 'resume' continues from last run, 'overwrite' recreates products (default: resume)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCRIPT_VERSION}"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log, args.verbose)

    print(f"Starting {SCRIPT_VERSION}")
    print("=" * 60)

    # Validate input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file does not exist: {args.input}", file=sys.stderr)
        return 1

    # Load configuration
    cfg = load_config()

    # Validate Shopify credentials
    if not cfg.get("SHOPIFY_STORE_URL", "").strip():
        print("Error: SHOPIFY_STORE_URL not configured in config.json", file=sys.stderr)
        return 1

    if not cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip():
        print("Error: SHOPIFY_ACCESS_TOKEN not configured in config.json", file=sys.stderr)
        return 1

    # Update config with CLI arguments
    cfg["INPUT_FILE"] = args.input
    cfg["PRODUCT_OUTPUT_FILE"] = args.output
    cfg["COLLECTIONS_OUTPUT_FILE"] = args.collections_output or "collections.json"
    cfg["EXECUTION_MODE"] = args.mode

    if args.log:
        cfg["LOG_FILE"] = args.log

    # Save updated config
    save_config(cfg)

    print(f"Input file: {args.input}")
    print(f"Output file: {args.output}")
    print(f"Collections file: {cfg['COLLECTIONS_OUTPUT_FILE']}")
    print(f"Execution mode: {args.mode}")
    print("=" * 60)

    try:
        # Run processing
        process_products(cfg, print_status, execution_mode=args.mode)
        print("=" * 60)
        print("Processing completed successfully!")
        return 0
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user.", file=sys.stderr)
        return 130
    except Exception as e:
        logging.exception("Fatal error during processing:")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
