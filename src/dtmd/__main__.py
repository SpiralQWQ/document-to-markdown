"""`python -m dtmd` 入口 → 转发到 cli.main。"""
from dtmd.cli import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
