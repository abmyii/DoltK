import sqlalchemy
import pandas as pd
import time

from sqlakeyset import get_page, select_page
from sqlalchemy.orm import Session

from sqlalchemy.ext.automap import automap_base
from sqlalchemy import select, Table, MetaData, create_engine, text

engine = create_engine('mysql+pymysql://root:@localhost:3306/hospital_price_transparency_v3', execution_options=dict(stream_results=True))
metadata = MetaData(bind=None)
diff_table = Table('dolt_diff_hospitals', metadata, autoload_with=engine)

for table in pd.read_sql_query('SELECT * FROM dolt_diff_prices', engine, chunksize=100000):
    t = time.time()
    print(table)
    print(time.time()-t)

import sys
sys.exit(0)

session = Session(engine)

q = session.query(diff_table).where(text('from_commit="1mj3g3iqk1m8do0u495j3fnif60133p7" AND to_commit="uri5bv8oasoq7ipcku26nnk9h94n0juq"'))
print(q, type(q))

# gets the first page
page1 = get_page(q, per_page=20)
print(q.statement)

# gets the key for the next page
next_page = page1.paging.next
print(next_page)

# gets the second page
page2 = get_page(q, per_page=20, page=next_page)
print(page2)

# returning to the first page, getting the key
previous_page = page2.paging.previous

# the first page again, backwards from the previous page
page1 = get_page(q, per_page=20, page=previous_page)

# what if new items were added at the start?
if page1.paging.has_previous:

    # go back even further
    previous_page = page1.paging.previous
    page1 = get_page(q, per_page=20, page=previous_page)
