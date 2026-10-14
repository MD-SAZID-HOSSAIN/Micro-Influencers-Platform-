#!/usr/bin/env python
import sys


def main():
    from config.bootstrap import configure

    configure()  # production settings unless the environment (or .env) says otherwise
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
