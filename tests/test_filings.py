import io, zipfile
import city_filings as F

IDX = """Description:           Master Index of EDGAR Dissemination Feed by Form Type
Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------------------------------------------
SCHEDULE 13D      ACME CORP                                                     111         2025-10-02  edgar/data/111/0001-25-1.txt
SCHEDULE 13D      BIG ACTIVIST FUND LP                                          999         2025-10-02  edgar/data/111/0001-25-1.txt
SCHEDULE 13D/A    ACME CORP                                                     111         2025-10-09  edgar/data/111/0001-25-2.txt
4                 ACME CORP                                                     111         2025-10-03  edgar/data/111/0001-25-3.txt
"""

def test_form_idx_and_13d():
    rows = F.parse_form_idx(IDX)
    assert len(rows) == 4 and rows[0][0] == 'SCHEDULE 13D' and rows[0][2] == 111
    assert F.initial_13d(rows, {111: 'ACME'}) == [('ACME', '2025-10-02')]   # amendment ignored, filer not tradable

def zbytes():
    b = io.BytesIO(); z = zipfile.ZipFile(b, 'w')
    z.writestr('SUBMISSION.tsv', 'ACCESSION_NUMBER\tFILING_DATE\tDOCUMENT_TYPE\tISSUERTRADINGSYMBOL\nA1\t02-OCT-2025\t4\tacme\nA2\t03-OCT-2025\t4\tACME\nA3\t03-OCT-2025\t3\tACME\n')
    z.writestr('REPORTINGOWNER.tsv', 'ACCESSION_NUMBER\tRPTOWNERCIK\nA1\t5\nA2\t6\nA3\t7\n')
    z.writestr('NONDERIV_TRANS.tsv', 'ACCESSION_NUMBER\tTRANS_CODE\tTRANS_ACQUIRED_DISP_CD\tTRANS_SHARES\tTRANS_PRICEPERSHARE\n'
               'A1\tP\tA\t10000\t20\nA2\tP\tA\t5000\t20\nA2\tS\tD\t100\t20\nA3\tP\tA\t99999\t20\n')
    z.close(); return b.getvalue()

def test_insider_buys_and_cluster():
    buys = F.insider_buys(zbytes())
    assert [(b['sym'], b['owner'], b['filed'], b['value']) for b in buys] == [('ACME', '5', '2025-10-02', 200000.0), ('ACME', '6', '2025-10-03', 100000.0)]
    cal = ['2025-10-01', '2025-10-02', '2025-10-03', '2025-10-06']
    assert F.clusters(buys, cal) == [('ACME', '2025-10-03')]                 # completed by the second insider's filing
    assert F.clusters(buys[:1], cal) == []

def test_trade_time_and_stop():
    n = 40
    S = dict(d=[f'd{k:02d}' for k in range(n)], o=[10.0] * n, h=[10.2] * n, l=[9.8] * n, c=[10.0] * n, v=[1] * n)
    r = F.trade(S, 10, 'zzz'); assert r[2] == 11 and r[3] == 30 and r[4] == 'time'
    S['c'][15] = 8.0; S['o'][16] = 7.9
    r = F.trade(S, 10, 'zzz'); assert r[4] == 'stop' and r[1] == 7.9 and r[3] == 16
    assert F.trade(S, 30, S['d'][-1]) is None                               # still running at the end of the data
