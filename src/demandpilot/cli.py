"""Command line entry point for reproducible pipeline operations."""

import argparse

from demandpilot.db import check_database, initialize_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="DemandPilot pipeline")
    parser.add_argument("command", choices=["init-db", "check-db", "prepare-data"])
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args()
    if args.command == "init-db":
        initialize_schema()
        print("Database schema initialized.")
    elif args.command == "check-db":
        print(check_database())
    else:
        from demandpilot.data.pipeline import prepare_data

        prepare_data(args.settings)


if __name__ == "__main__":
    main()
