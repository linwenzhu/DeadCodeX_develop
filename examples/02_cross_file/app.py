"""Command-line entry point for the cross-file analysis example."""

from shop.service import checkout as execute_checkout


def main():
    return execute_checkout("Ada", [12.0, 8.0])


if __name__ == "__main__":
    print(main())
