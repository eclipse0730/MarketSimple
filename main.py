# -*- coding: utf-8 -*-
"""시장별 실행 진입점."""

import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(description="Market Brief", add_help=False)
    ap.add_argument("--market", choices=["kr", "us"], default="kr", help="시장 선택 (기본: kr)")
    ap.add_argument("-h", "--help", action="store_true", help="show this help message and exit")
    args, rest = ap.parse_known_args(argv)

    if args.market == "kr":
        from kr.main import main as kr_main

        if args.help:
            rest = ["--help"]
        return kr_main(rest)

    from us.main import main as us_main

    if args.help:
        rest = ["--help"]
    return us_main(rest)


if __name__ == "__main__":
    main()
