"""Command line entry point for reproducible pipeline operations."""

import argparse

from demandpilot.db import check_database, initialize_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="DemandPilot pipeline")
    parser.add_argument("command", choices=["init-db", "check-db", "prepare-data", "train", "predict"])
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args()
    if args.command == "init-db":
        initialize_schema()
        print("Database schema initialized.")
    elif args.command == "check-db":
        print(check_database())
    elif args.command == "prepare-data":
        from demandpilot.data.pipeline import prepare_data

        prepare_data(args.settings)
    elif args.command == "train":
        from demandpilot.modeling.train import train_models

        train_models(args.settings)
    else:
        from demandpilot.modeling.predict import predict_latest

        predict_latest()


if __name__ == "__main__":
    main()
