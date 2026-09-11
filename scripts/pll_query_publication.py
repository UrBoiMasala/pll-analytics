"""Run example SQL against final views without requiring a DuckDB CLI installation."""
from pll_build_publication import ROOT,connect

def main():
    con=connect()
    for statement in con.extract_statements((ROOT/'sql/publication_examples.sql').read_text()):
        if statement.query.strip():
            result=con.execute(statement).df()
            print(statement.query.strip().splitlines()[0]);print(result.head(10).to_string(index=False));print()
    con.close()
if __name__=='__main__':main()
