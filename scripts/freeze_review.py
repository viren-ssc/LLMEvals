import sys

from canadianness_eval.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["freeze-review", *sys.argv[1:]]))
