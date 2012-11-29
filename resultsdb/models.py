from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, \
    Float, PickleType, ForeignKey, Text

Base = declarative_base()

class Configuration(Base):
  __tablename__ = 'configuration'
  id   = Column(Integer, primary_key=True)
  hash = Column(String(32))
  data = Column(PickleType)

class MachineClass(Base):
  __tablename__ = 'machine_class'
  id            = Column(Integer, primary_key=True)
  name          = Column(String(128))

class Machine(Base):
  __tablename__ = 'machine'
  id            = Column(Integer, primary_key=True)
  name          = Column(String(128))
  cpu           = Column(String(32))
  memory        = Column(Integer)
  machine_class = Column(ForeignKey(MachineClass.id))

class InputClass(Base):
  __tablename__ = 'program_input_class'
  id   = Column(Integer, primary_key=True)
  name = Column(String(128))
  size = Column(Integer)

class Input(Base):
  __tablename__ = 'program_input'
  id            = Column(Integer, primary_key=True)
  state         = Column(Enum('ANY_MACHINE', 'SINGLE_MACHINE', 'DELETED'))
  input_class   = Column(ForeignKey(InputClass.id))
  machine       = Column(ForeignKey(MachineClass.id))
  path          = Column(Text)
  extra         = Column(PickleType)

class TuningRun(Base):
  __tablename__ = 'tuning_run'
  id = Column(Integer, primary_key=True)
  program_version = Column(String(128))
  start_date      = Column(DateTime)
  end_date        = Column(DateTime)
  settings        = Column(PickleType)

class Result(Base):
  __tablename__   = 'result'
  id              = Column(Integer, primary_key=True)
  state           = Column(Enum('OK', 'TIMEOUT', 'ERROR'))
  configuration   = Column(ForeignKey(Configuration.id))
  machine         = Column(ForeignKey(Machine.id))
  input           = Column(ForeignKey(Input.id))
  tuning_run      = Column(ForeignKey(TuningRun.id))
  time            = Column(Float)
  accuracy        = Column(Float)
  confidence      = Column(Float)
  extra           = Column(PickleType)
  collection_date = Column(DateTime)
  collection_cost = Column(Float)

class DesiredResult(Base):
  __tablename__ = 'desired_result'
  id            = Column(Integer, primary_key=True)
  state         = Column(Enum('REQUESTED', 'RUNNING', 'COMPLETE', 'ABORTED'))
  configuration = Column(ForeignKey(Configuration.id))
  generation    = Column(Integer)
  priority      = Column(Float)
  requestor     = Column(String(128))
  tuning_run    = Column(ForeignKey(TuningRun.id))
  request_date  = Column(DateTime)
  start_date    = Column(DateTime)
  result        = Column(ForeignKey(Result.id))

if __name__ == '__main__':
  engine = create_engine('sqlite:///:memory:', echo=True)
  Base.metadata.create_all(engine) 

