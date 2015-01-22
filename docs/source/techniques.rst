.. currentmodule:: opentuner.search.technique

********************
Current Techniques
********************

=================================
Composable Search Techniques
=================================

ComposableSearchTechnique allows for composition between the seearch technique and any operators. Creating a ComposableSearchTechnique requires implementing 3 methods:

 * :meth:`minimum_number_of_parents <ComposableSearchTechnique.minimum_number_of_parents>`
 * :meth:`get_parents <ComposableSearchTechnique.get_parents>`
 * :meth:`update_population <ComposableSearchTechnique.update_population>`

Additionally, the following methods may be overridden for further customization

 * :meth:`make_population_member <ComposableSearchTechnique.make_population_member>`
 * :meth:`select_parameters <ComposableSearchTechnique.select_parameters>`
 * :meth:`get_default_operator <ComposableSearchTechnique.get_default_operator>`

The following methods are useful when choosing parents or updating the population:

 * :meth:`lt <ComposableSearchTechnique.lt>`
 * :meth:`lte <ComposableSearchTechnique.lte>`
 * :meth:`get_global_best_configuration <ComposableSearchTechnique.get_global_best_configuration>`

.. autoclass:: ComposableSearchTechnique

	.. automethod:: minimum_number_of_parents

	.. automethod:: get_parents

	.. automethod:: update_population

	.. automethod:: make_population_member

	.. automethod:: select_parameters

	.. automethod:: get_default_operator

	.. automethod:: lt

	.. automethod:: lte

	.. automethod:: get_global_best_configuration
