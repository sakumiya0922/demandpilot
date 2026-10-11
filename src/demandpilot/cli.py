"""Command line entry point for reproducible pipeline operations."""

import argparse

from demandpilot.db import check_database, initialize_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="DemandPilot pipeline")
    parser.add_argument("command", choices=["init-db", "check-db"])
    args = parser.parse_args()
    if args.command == "init-db":
        initialize_schema()
        print("Database schema initialized.")
    else:
        print(check_database())


if __name__ == "__main__":
    main()
