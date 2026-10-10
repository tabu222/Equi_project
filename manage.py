#!/usr/bin/env python
"""Công cụ dòng lệnh của Django: chạy server, chạy test, tạo dữ liệu demo..."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
