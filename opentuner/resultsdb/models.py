from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm import relationship, backref
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Enum,
    Float, PickleType, ForeignKey, Text, func, Index
  )
import sqlalchemy
import re

class Base(object):
  @declared_attr
  def __tablename__(cls):
    '''convert camel case to underscores'''
    return re.sub(r'([a-z])([A-Z])', r'\1_\2', cls.__name__).lower()

  id = Column(Integer, primary_key=True, index=True)

Base = declarative_base(cls=Base)

class Program(Base):
  project = Column(String(128))
  name    = Column(String(128))

  @classmethod
  def get(cls, session, project, name):
    try:
      session.flush()
      return session.query(Program).filter_by(project=project, name=name).one()
    except sqlalchemy.orm.exc.NoResultFound:
      t = Program(project=project, name=name)
      session.add(t)
      return t

class ProgramVersion(Base):
  program_id = Column(ForeignKey(Program.id))
  program    = relationship(Program, backref='versions')
  version    = Column(String(128))

  @property
  def name(self):
    return program.name

  @property
  def project(self):
    return program.project

  @classmethod
  def get(cls, session, project, name, version):
    program = Program.get(session, project, name)
    try:
      session.flush()
      return session.query(ProgramVersion).filter_by(program=program,
                                                     version=version).one()
    except sqlalchemy.orm.exc.NoResultFound:
      t = ProgramVersion(program=program, version=version)
      session.add(t)
      return t

class Configuration(Base):
  program_id = Column(ForeignKey(Program.id))
  program    = relationship(Program)
  hash       = Column(String(64))
  data       = Column(PickleType)

  @classmethod
  def get(cls, session, program, hashv, datav):
    try:
      session.flush()
      return (session
                .query(Configuration)
                .filter_by(program=program, hash=hashv)
                .one())
    except sqlalchemy.orm.exc.NoResultFound:
      t = Configuration(program=program, hash=hashv, data=datav)
      session.add(t)
      return t

Index('ix_configuration_custom1', Configuration.program_id, Configuration.hash)

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
  program_id = Column(ForeignKey(Program.id))
  program    = relationship(Program, backref='inputs')

  name       = Column(String(128))
  size       = Column(Integer)

  @classmethod
  def get(cls, session, program, name='default', size=-1):
    try:
      session.flush()
      return session.query(InputClass).filter_by(program=program,
                                                 name=name,
                                                 size=size).one()
    except sqlalchemy.orm.exc.NoResultFound:
      t = InputClass(program=program, name=name, size=size)
      session.add(t)
      return t

class Input(Base):
  #state          = Column(Enum('ANY_MACHINE', 'SINGLE_MACHINE', 'DELETED'),
  #                        default='ANY_MACHINE', name='t_input_state')

  input_class_id = Column(ForeignKey(InputClass.id))
  input_class    = relationship(InputClass, backref='inputs')

  #optional, set only for state='SINGLE_MACHINE'
  #machine_id     = Column(ForeignKey(MachineClass.id))
  #machine        = relationship(MachineClass, backref='inputs')

  #optional, for use by InputManager
  path           = Column(Text)
  extra          = Column(PickleType)

class TuningRun(Base):
  uuid = Column(String(32), index=True, unique=True)

  program_version_id = Column(ForeignKey(ProgramVersion.id))
  program_version    = relationship(ProgramVersion, backref='tuning_runs')

  machine_class_id = Column(ForeignKey(MachineClass.id))
  machine_class    = relationship(MachineClass, backref='tuning_runs')

  input_class_id = Column(ForeignKey(InputClass.id))
  input_class    = relationship(InputClass, backref='tuning_runs')

  name      = Column(String(128), default='unnamed')
  args      = Column(PickleType)
  objective = Column(PickleType)

  state      = Column(Enum('QUEUED', 'RUNNING', 'COMPLETE', 'ABORTED',
                                 name='t_tr_state'),
                            default = 'QUEUED')
  start_date = Column(DateTime, default=func.now())
  end_date   = Column(DateTime)

  final_config_id = Column(ForeignKey(Configuration.id))
  final_config    = relationship(Configuration)

  #__mapper_args__ = {'primary_key': uuid}

  @property
  def program(self):
    return self.program_version.program

class Result(Base):
  #set by MeasurementDriver:
  configuration_id= Column(ForeignKey(Configuration.id))
  configuration   = relationship(Configuration)

  machine_id      = Column(ForeignKey(Machine.id))
  machine         = relationship(Machine, backref='results')

  input_id        = Column(ForeignKey(Input.id))
  input           = relationship(Input, backref='results')

  tuning_run_id   = Column(ForeignKey(TuningRun.id), index=True)
  tuning_run      = relationship(TuningRun, backref='results')

  collection_date = Column(DateTime, default=func.now())
  collection_cost = Column(Float)

  #set by MeasurementInterface:
  state           = Column(Enum('OK', 'TIMEOUT', 'ERROR',
                                name='t_result_state'),
                           default='OK')
  time            = Column(Float)
  accuracy        = Column(Float)
  energy          = Column(Float)
  size            = Column(Float)
  confidence      = Column(Float)
  #extra           = Column(PickleType)

  #set by SearchDriver
  was_new_best    = Column(Boolean)

Index('ix_result_custom1', Result.tuning_run_id, Result.was_new_best)

class DesiredResult(Base):
  #set by the technique:
  configuration_id = Column(ForeignKey(Configuration.id))
  configuration    = relationship(Configuration)
  limit            = Column(Float)

  #set by the search driver
  priority         = Column(Float)
  tuning_run_id    = Column(ForeignKey(TuningRun.id))
  tuning_run       = relationship(TuningRun, backref='desired_results')
  generation       = Column(Integer)
  requestor        = Column(String(128))
  request_date     = Column(DateTime, default=func.now())

  #set by the measurement driver
  state            = Column(Enum('UNKNOWN', 'REQUESTED', 'RUNNING',
                                 'COMPLETE', 'ABORTED',
                                 name="t_dr_state"),
                            default = 'UNKNOWN')
  result_id        = Column(ForeignKey(Result.id), index=True)
  result           = relationship(Result, backref='desired_results')
  start_date       = Column(DateTime)

 #input_id        = Column(ForeignKey(Input.id))
 #input           = relationship(Input, backref='desired_results')

Index('ix_desired_result_custom1', DesiredResult.tuning_run_id,
                                   DesiredResult.generation)

Index('ix_desired_result_custom2', DesiredResult.tuning_run_id,
                                   DesiredResult.configuration_id)

if __name__ == '__main__':
  #test:
  engine = create_engine('sqlite:///:memory:', echo=True)
  Base.metadata.create_all(engine) 

