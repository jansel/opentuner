from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from models import Base
import logging
import time
from pprint import pprint

log = logging.getLogger(__name__)

if False:  # profiling of queries
  import atexit
  from sqlalchemy import event
  from collections import Counter
  from sqlalchemy.engine import Engine
  the_query_totals = Counter()

  @event.listens_for(Engine, "before_cursor_execute")
  def before_cursor_execute(conn, cursor, statement,
                            parameters, context, executemany):
      context._query_start_time = time.time()

  @event.listens_for(Engine, "after_cursor_execute")
  def after_cursor_execute(conn, cursor, statement,
                           parameters, context, executemany):
      total = time.time() - context._query_start_time
      the_query_totals[statement] += total

  @atexit.register
  def report():
    pprint(the_query_totals.most_common(10))


def connect(dbstr):
  engine = create_engine(dbstr, echo = False)
  Base.metadata.create_all(engine)
  Session = scoped_session(sessionmaker(autocommit=False,
                                        autoflush=False,
                                        bind=engine))
  return engine, Session

