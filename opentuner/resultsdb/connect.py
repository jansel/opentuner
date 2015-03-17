from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from models import Base, _Meta
import logging
import time
from pprint import pprint

log = logging.getLogger(__name__)

DB_VERSION = "0.0"

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
  connection = engine.connect()

  #handle case that the db was initialized before a version table existed yet
  if engine.dialect.has_table(connection, "program"):
    # if there are existing tables
    if not engine.dialect.has_table(connection, "_meta"):
      # if no version table, assume outdated db version and error
      connection.close()
      raise Exception("Your opentuner database is currently out of date. Save a back up and reinitialize")

  # else if we have the table already, make sure version matches
  if engine.dialect.has_table(connection, "_meta"):
    Session = scoped_session(sessionmaker(autocommit=False,
                                          autoflush=False,
                                          bind=engine))
    version = _Meta.get_version(Session)
    if not DB_VERSION == version:
      raise Exception('Your opentuner database version {} is out of date with the current version {}'.format(version, DB_VERSION))

  Base.metadata.create_all(engine)

  Session = scoped_session(sessionmaker(autocommit=False,
                                        autoflush=False,
                                        bind=engine))
  # mark database with current version
  _Meta.add_version(Session, DB_VERSION)
  Session.commit()

  return engine, Session

