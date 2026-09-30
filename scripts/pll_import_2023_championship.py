"""Compatibility entry point for the reviewed 2023 Championship Series import."""
import argparse
from pll_import_championship import main
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fetch',action='store_true')
    main(fetch=parser.parse_args().fetch,year=2023)
