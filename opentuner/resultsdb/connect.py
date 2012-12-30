
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from models import Base

def connect(dbstr):
  engine = create_engine(dbstr)
  Base.metadata.create_all(engine) 
  Session = scoped_session(sessionmaker(autocommit=False,
                                        autoflush=False,
                                        bind=engine))
  return engine, Session

