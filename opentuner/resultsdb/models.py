from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm import relationship, backref
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, \
    Float, PickleType, ForeignKey, Text, func
import sqlalchemy
import re

class Base(object):
  @declared_attr
  def __tablename__(cls):
    '''convert camel case to underscores'''
    return re.sub(r'([a-z])([A-Z])', r'\1_\2', cls.__name__).lower()

  id = Column(Integer, primary_key=True)

Base = declarative_base(cls=Base)

class Configuration(Base):
  hash = Column(String(64))
  data = Column(PickleType)

  @classmethod
  def get(cls, session, hashv, datav):
    try:
      session.flush()
      return session.query(Configuration).filter_by(hash=hashv).one()
    except sqlalchemy.orm.exc.NoResultFound:
      t = Configuration()
      t.hash = hashv
      t.data = datav
      session.add(t)
      return t 

class MachineClass(Base):
  name          = Column(String(128))

  @classmethod
  def get(cls, session, name):
    try:
      session.flush()
      return session.query(MachineClass).filter_by(name=name).one()
    except sqlalchemy.orm.exc.NoResultFound:
      t = MachineClass(name=name)
      session.add(t)
      return t

class Machine(Base):
  name             = Column(String(128))

  cpu              = Column(String(128))
  cores            = Column(Integer)
  memory_gb        = Column(Float)

  machine_class_id = Column(ForeignKey(MachineClass.id))
  machine_class    = relationship(MachineClass, backref='machines')

class InputClass(Base):
  name = Column(String(128))
  size = Column(Integer)

  @classmethod
  def get(cls, session, name='default', size=-1):
    try:
      session.flush()
      return session.query(InputClass).filter_by(name=name, size=size).one()
    except sqlalchemy.orm.exc.NoResultFound:
      t = InputClass(name=name, size=size)
      session.add(t)
      return t

class Input(Base):
  #state          = Column(Enum('ANY_MACHINE', 'SINGLE_MACHINE', 'DELETED'),
  #                        default='ANY_MACHINE')

  input_class_id = Column(ForeignKey(InputClass.id))
  input_class    = relationship(InputClass, backref='inputs')

  #optional, set only for state='SINGLE_MACHINE'
  #machine_id     = Column(ForeignKey(MachineClass.id))
  #machine        = relationship(MachineClass, backref='inputs')

  #optional, for use by InputManager
  path           = Column(Text)
  extra          = Column(PickleType)

class TuningRun(Base):
  name            = Column(String(128), default='unnamed')
  program_version = Column(String(128), default='unknown')
  args            = Column(PickleType)

  state            = Column(Enum('QUEUED', 'RUNNING', 'COMPLETE', 'ABORTED'),
                            default = 'QUEUED')
  start_date      = Column(DateTime, default=func.now())
  end_date        = Column(DateTime)

class Result(Base):
  #set by MeasurementDriver:
  configuration_id= Column(ForeignKey(Configuration.id))
  configuration   = relationship(Configuration)

  machine_id      = Column(ForeignKey(Machine.id))
  machine         = relationship(Machine, backref='results')

  input_id        = Column(ForeignKey(Input.id))
  input           = relationship(Input, backref='results')

  tuning_run_id   = Column(ForeignKey(TuningRun.id))
  tuning_run      = relationship(TuningRun, backref='results')

  collection_date = Column(DateTime, default=func.now())
  collection_cost = Column(Float)

  #set by MeasurementInterface:
  state           = Column(Enum('OK', 'TIMEOUT', 'ERROR'), default='OK')
  time            = Column(Float)
  accuracy        = Column(Float)
  confidence      = Column(Float)
  extra           = Column(PickleType)


class DesiredResult(Base):
  #set by the technique:
  configuration_id = Column(ForeignKey(Configuration.id))
  configuration    = relationship(Configuration)
  priority_raw     = Column(Float)

  #set by the search driver
  priority         = Column(Float)
  tuning_run_id    = Column(ForeignKey(TuningRun.id))
  tuning_run       = relationship(TuningRun, backref='desired_results') 
  generation       = Column(Integer)
  requestor        = Column(String(128))
  request_date     = Column(DateTime, default=func.now())

  #set by the measurement driver
  state            = Column(Enum('REQUESTED', 'RUNNING', 'COMPLETE', 'ABORTED'),
                            default = 'REQUESTED')
  result_id        = Column(ForeignKey(Result.id))
  result           = relationship(Result, backref='desired_results')
  start_date       = Column(DateTime)

class TechniqueAccounting(Base):
  tuning_run_id    = Column(ForeignKey(TuningRun.id))
  tuning_run       = relationship(TuningRun, backref='accounting') 
  generation       = Column(Integer)
  budget           = Column(Integer)
  name             = Column(String(128))
  start_date       = Column(DateTime, default=func.now())
  end_date         = Column(DateTime)

if __name__ == '__main__':
  #test:
  engine = create_engine('sqlite:///:memory:', echo=True)
  Base.metadata.create_all(engine) 

