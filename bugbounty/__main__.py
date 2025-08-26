"""
Main entry point for the bug bounty tool when run as a module.
Allows execution with 'python -m bugbounty'
"""

from .cli import main

if __name__ == "__main__":
    main()