"""Compatibility entrypoint for local runs and legacy imports."""

from server.app import app, main


if __name__ == "__main__":
    main()
