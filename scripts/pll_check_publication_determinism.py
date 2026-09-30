"""Rebuild twice in fresh directories and compare every exported byte."""
import argparse
import hashlib
import tempfile
from pathlib import Path
import pandas as pd
from pll_build_publication import ROOT,connect,export,export_splits
from pll_publication_catalog import write_dictionary

def verify():
    with tempfile.TemporaryDirectory(prefix='pll-publication-') as tmp:
        a,b=Path(tmp)/'a',Path(tmp)/'b'
        for out in [a,b]:
            con=connect();export(con,out);write_dictionary(out);con.close();export_splits(out)
        left={p.relative_to(a) for p in a.rglob('*.csv')};right={p.relative_to(b) for p in b.rglob('*.csv')}
        if left!=right: raise AssertionError('Rebuild file sets differ')
        rows=[]
        for rel in sorted(left):
            data=(a/rel).read_bytes();same=data==(b/rel).read_bytes()
            published=ROOT/'data/publication'/rel
            current=published.exists() and data==published.read_bytes()
            rows.append(dict(artifact=str(rel),sha256=hashlib.sha256(data).hexdigest(),rebuild_match=same,publication_match=current))
        report=pd.DataFrame(rows)
        if not (report.rebuild_match & report.publication_match).all(): raise AssertionError(report.to_string(index=False))
        return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
    report=verify();print(f'{len(report)}/{len(report)} deterministic exports match both rebuilds and publication')
    if args.write_report: report.to_csv(ROOT/'data/publication/determinism_report.csv',index=False)
if __name__=='__main__':main()
