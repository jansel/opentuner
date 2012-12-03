from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, \
    Float, PickleType, ForeignKey, Text, func
import re

class Base(object):
  @declared_attr
  def __tablename__(cls):
    '''convert camel case to underscores'''
    return re.sub(r'([a-z])([A-Z])', r'\1_\2', cls.__name__).lower()

  id = Column(Integer, primary_key=True)

Base = declarative_base(cls=Base)

class Configuration(Base):
  hash = Column(String(32))
  data = Column(PickleType)

class MachineClass(Base):
  name          = Column(String(128))

class Machine(Base):
  name          = Column(String(128))
  cpu           = Column(String(32))
  memory        = Column(Integer)
  machine_class = Column(ForeignKey(MachineClass.id))

class InputClass(Base):
  name = Column(String(128))
  size = Column(Integer)

class Input(Base):
  state         = Column(Enum('ANY_MACHINE', 'SINGLE_MACHINE', 'DELETED'))
  input_class   = Column(ForeignKey(InputClass.id))
  machine       = Column(ForeignKey(MachineClass.id))
  path          = Column(Text)
  extra         = Column(PickleType)

class TuningRun(Base):
  name            = Column(String(128), default='unnamed')
  program_version = Column(String(128), default='unknown')
  start_date      = Column(DateTime, default=func.now())
  end_date        = Column(DateTime)
  settings        = Column(PickleType)

class Result(Base):
  state           = Column(Enum('OK', 'TIMEOUT', 'ERROR'), default='OK')
  configuration   = Column(ForeignKey(Configuration.id))
  machine         = Column(ForeignKey(Machine.id))
  input           = Column(ForeignKey(Input.id))
  tuning_run      = Column(ForeignKey(TuningRun.id))
  time            = Column(Float)
  accuracy        = Column(Float)
  confidence      = Column(Float)
  extra           = Column(PickleType)
  collection_date = Column(DateTime, default=func.now())
  collection_cost = Column(Float)

class DesiredResult(Base):
  state         = Column(Enum('REQUESTED', 'RUNNING', 'COMPLETE', 'ABORTED'), default = 'REQUESTED')
  configuration = Column(ForeignKey(Configuration.id))
  generation    = Column(Integer)
  priority      = Column(Float)
  priority_raw  = Column(Float)
  requestor     = Column(String(128))
  tuning_run    = Column(ForeignKey(TuningRun.id))
  request_date  = Column(DateTime, default=func.now())
  start_date    = Column(DateTime)
  result        = Column(ForeignKey(Result.id))

if __name__ == '__main__':
  #test:
  engine = create_engine('sqlite:///:memory:', echo=True)
  Base.metadata.create_all(engine) 

