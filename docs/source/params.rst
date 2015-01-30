.. currentmodule:: opentuner.search.manipulator

****************
Parameters
****************

This will be an overview of parameters in OpenTuner.

Each Parameter instance is created with a name. Most methods in parameters operate on configurations, dict-like objects spawned by the ConfigurationManipulator. Configurations contain values corresponding to a collection of instances of named parameters.

A Parameter’s methods may mutate the value in a configuration corresponding to the name of the particular parameter instance. These methods are called operators.

==============================
Parameter Types and Operators
==============================

Each parameter has a set of operators. These operators take in a set of parent configurations and mutate the corresponding parameter value in the first configuration according to the parent values. Operators form the set of available transformations for search techniques to generate new configurations to test.

Operator methods can be identified by the prefix 'op#_', where # is the number of required input configurations. The prefix 'opn\_' specifies an arbitrary number of input configurations, as a list. The first argument into an operator is always the configuration that will be mutated. This is followed by the required parent configurations, then any required arguments, and finally optional arguments.

Any operators defined for a Parameter are inherited by its subclasses.

-----------------
Parameter
-----------------
This is an abstract base interface for parameters.

.. autoclass:: Parameter

	.. automethod:: op1_randomize

	.. automethod:: op3_swarm

	.. automethod:: op4_set_linear

	.. automethod:: opn_stochastic_mix


-------------------------
Primitive Parameter
-------------------------
.. autoclass:: PrimitiveParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Parameter.op1_randomize`,
	:meth:`Parameter.op3_swarm`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_normal_mutation

	**This paragraph can have examples for the above operator**

	.. automethod:: op4_set_linear


------------------------
Numeric Parameter
------------------------
.. autoclass:: NumericParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`Parameter.op3_swarm`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize

	.. automethod:: op1_scale

	.. automethod:: op3_difference

	.. automethod:: opn_sum


------------------------
Integer Parameter
------------------------
.. autoclass:: IntegerParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`NumericParameter.op1_randomize`,
	:meth:`NumericParameter.op1_scale`,
	:meth:`NumericParameter.op3_difference`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`,
	:meth:`NumericParameter.opn_sum`

	.. automethod:: op3_swarm


------------------------
Float Parameter
------------------------
.. autoclass:: FloatParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`NumericParameter.op1_randomize`,
	:meth:`NumericParameter.op1_scale`,
	:meth:`NumericParameter.op3_difference`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`,
	:meth:`NumericParameter.opn_sum`

	.. automethod:: op3_swarm


------------------------
ScaledNumericParameter
------------------------
.. autoclass:: ScaledNumericParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`NumericParameter.op1_randomize`,
	:meth:`NumericParameter.op1_scale`,
	:meth:`NumericParameter.op3_difference`,
	:meth:`Parameter.op3_swarm`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`,
	:meth:`NumericParameter.opn_sum`


------------------------
LogIntegerParameter
------------------------
.. autoclass:: LogIntegerParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`NumericParameter.op1_randomize`,
	:meth:`NumericParameter.op1_scale`,
	:meth:`NumericParameter.op3_difference`,
	:meth:`FloatParameter.op3_swarm`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`,
	:meth:`NumericParameter.opn_sum`


------------------------
LogFloatParameter
------------------------
.. autoclass:: LogFloatParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`NumericParameter.op1_randomize`,
	:meth:`NumericParameter.op1_scale`,
	:meth:`NumericParameter.op3_difference`,
	:meth:`FloatParameter.op3_swarm`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`,
	:meth:`NumericParameter.opn_sum`


------------------------
PowerOfTwoParameter
------------------------
.. autoclass:: LogFloatParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`PrimitiveParameter.op1_normal_mutation`,
	:meth:`NumericParameter.op1_randomize`,
	:meth:`NumericParameter.op1_scale`,
	:meth:`NumericParameter.op3_difference`,
	:meth:`IntegerParameter.op3_swarm`,
	:meth:`PrimitiveParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`,
	:meth:`NumericParameter.opn_sum`


------------------------
Complex Parameter
------------------------
.. autoclass:: ComplexParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Parameter.op3_swarm`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize

	.. automethod:: op4_set_linear


------------------------
Boolean Parameter
------------------------
.. autoclass:: BooleanParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Parameter.op3_swarm`,
	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_flip

	.. automethod:: op1_randomize

	.. automethod:: op3_swarm

--------------------------
Switch Parameter
--------------------------
.. autoclass:: SwitchParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Parameter.op3_swarm`,
	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize

--------------------------
Enum Parameter
--------------------------
.. autoclass:: EnumParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Parameter.op3_swarm`,
	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize


--------------------------
Permutation Parameter
--------------------------
.. autoclass:: PermutationParameter
	:show-inheritance:

	*Inherited Operators:*

	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize

	.. automethod:: op1_small_random_change

	.. automethod:: op2_random_swap

	.. automethod:: op2_random_invert

	.. automethod:: op3_cross

	.. automethod:: op3_cross_PX

	.. automethod:: op3_cross_PMX

	.. automethod:: op3_cross_CX

	.. automethod:: op3_cross_OX1

	.. automethod:: op3_cross_OX3

	.. automethod:: op3_swarm

--------------------------
Array
--------------------------
.. autoclass:: Array
	:show-inheritance:

	*Inherited Operators:*

	:meth:`ComplexParameter.op1_randomize`,
	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op3_cross

	.. automethod:: op3_swarm


--------------------------
BooleanArray
--------------------------
.. autoclass:: BooleanArray
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Array.op3_cross`,
	:meth:`Array.op3_swarm`,
	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize

	.. automethod:: op3_swarm_parallel


--------------------------
FloatArray
--------------------------
.. autoclass:: FloatArray
	:show-inheritance:

	*Inherited Operators:*

	:meth:`Array.op3_cross`,
	:meth:`Array.op3_swarm`,
	:meth:`ComplexParameter.op4_set_linear`,
	:meth:`Parameter.opn_stochastic_mix`

	.. automethod:: op1_randomize

	.. automethod:: op3_swarm_parallel



