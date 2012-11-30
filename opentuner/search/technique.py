
import abc

class SearchTechnique(object):
  __metaclass__ = abc.ABCMeta
  
  @abc.abstractmethod
  def search_suggestions(self, search_driver, manipulator, budget):
    """return a list of resultsdb.models.DesiredResult objects based on past performance"""
    return


class PureRandom(SearchTechnique):
  __metaclass__ = abc.ABCMeta
  
  def search_suggestions(self, db, search_driver, manipulator, budget):
    """return a list of resultsdb.models.DesiredResult objects based on past performance"""
    return


