"""
CLI utility functions for applying command-line argument overrides to config.
"""


def apply_cli_overrides(cfg, args):
    """
    Apply CLI argument overrides to the config dictionary.

    Args:
        cfg: Configuration dictionary to update
        args: Parsed argparse namespace object
    """
    if getattr(args, 'use_input_quantities', False):
        cfg["USE_INPUT_QUANTITIES"] = True
