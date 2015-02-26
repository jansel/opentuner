---
layout: default
title: OpenTuner - Using OpenTuner
permalink: /tutorial/gettingstarted/index.html
---

Tutorial: Optimizing Block Matrix Multiplication
================================================

This tutorial assumes that you have checked out a copy of opentuner. For
guidelines on how to get opentuner set up, refer [here][setup].

[setup]: http://opentuner.org/tutorial/setup/

Identifying a Program to Autotune
---------------------------------

In order to do autotuning, you first need something to autotune. This will
normally be your own program that you want to make either fast or better in
some way.  For this tutorial we will use a blocked version of matrix multiply
as an example. We will use opentuner to find the optimal value of the block
size parameter.

We will autotune the sample code below(based off of modification of code
found [here][matrix-multiply-code]), making sure to take the block size as
a compile time constant to the program.

[matrix-multiply-code]: http://csapp.cs.cmu.edu/public/waside/waside-blocking.pdf

Save the sample code below to examples/tutorials/mmm_block.cpp

    #include <stdio.h>
    #include <cstdlib>

    #define N 100
    
    int main(int argc, const char** argv)
    {
    
      int n = BLOCK_SIZE * (N/BLOCK_SIZE);
      int a[N][N];
      int b[N][N];
      int c[N][N];
      int sum=0;
      for(int k1=0;k1<n;k1+=BLOCK_SIZE)
      {
          for(int j1=0;j1<n;j1+=BLOCK_SIZE)
          {
              for(int k1=0;k1<n;k1+=BLOCK_SIZE)
              {
                  for(int i=0;i<n;i++)
                  {
                      for(int j=j1;j<j1+BLOCK_SIZE;j++)
                      {
                          sum = c[i][j];
                          for(int k=k1;k<k1+BLOCK_SIZE;k++)
                          {
                              sum += a[i][k] * b[k][j];
                          }
                          c[i][j] = sum;
                      }
                  }
              }
          }
             }
      return 0;
    }

Creating a New Autotuner with Opentuner
------------------------------------
Now we need to create a program that uses OpenTuner to optimize the program we just saved.

Save the following code to examples/tutorials/mmm_tuner.py

    #!/usr/bin/env python
    #
    # Optimize blocksize of apps/mmm_block.cpp
    #
    # This is an extremely simplified version meant only for tutorials
    #
    import adddeps  # fix sys.path

    import opentuner
    from opentuner import ConfigurationManipulator
    from opentuner import IntegerParameter
    from opentuner import MeasurementInterface
    from opentuner import Result


    class GccFlagsTuner(MeasurementInterface):

      def manipulator(self):
        """
        Define the search space by creating a
        ConfigurationManipulator
        """
        manipulator = ConfigurationManipulator()
        manipulator.add_parameter(
          IntegerParameter('blockSize', 1, 10))
        return manipulator

      def run(self, desired_result, input, limit):
        """
        Compile and run a given configuration then
        return performance
        """
        cfg = desired_result.configuration.data

        gcc_cmd = 'g++ mmm_block.cpp '
        gcc_cmd += '-DBLOCK_SIZE='+ cfg['blockSize']
        gcc_cmd += ' -o ./tmp.bin'

        compile_result = self.call_program(gcc_cmd)
        assert compile_result['returncode'] == 0

        run_cmd = './tmp.bin'

        run_result = self.call_program(run_cmd)
        assert run_result['returncode'] == 0

        return Result(time=run_result['time'])

      def save_final_config(self, configuration):
        """called at the end of tuning"""
        print "Optimal block size written to mmm_final_config.json:", configuration.data
        self.manipulator().save_to_file(configuration.data,
                                        'mmm_final_config.json')


    if __name__ == '__main__':
      argparser = opentuner.default_argparser()
      GccFlagsTuner.main(argparser.parse_args())


This file consists of several components, each of which will be discussed in further detail below.

Tuning Programs have a general structure as follows:

    from opentuner import MeasurementInterface
    from opentuner import Result

Create an instance of class GccFlagsTuner, which tunes specified parameters using opentuner.
    class GccFlagsTuner(MeasurementInterface):

The manipulator method defines the variable search space by specifying parameters that should be tuned by this instance of GccFlagsTuner

    def manipulator(self):
      """
      Define the search space by creating a
      ConfigurationManipulator
      """
      manipulator = ConfigurationManipulator()
      manipulator.add_parameter(
        IntegerParameter('blockSize', 1, 10))
      return manipulator

The run method actually runs opentuner under the given configuration and returns the calculated performance under this configuration. In this example, the blockSize parameter to be tuned is input as a compile-time constant that takes on a value within the specified range each time it is run. However, opentuner also supports other methods of specifying these parameters that may be preferred in different use cases.

    def run(self, desired_result, input, limit):
      """
      Compile and run a given configuration then
      return performance
      """
      cfg = desired_result.configuration.data

      gcc_cmd = 'g++ mmm_block.cpp '
      gcc_cmd += '-DBLOCK_SIZE='+ cfg['blockSize']
      gcc_cmd += ' -o ./tmp.bin'

      compile_result = self.call_program(gcc_cmd)
      assert compile_result['returncode'] == 0

      run_cmd = './tmp.bin'

      run_result = self.call_program(run_cmd)
      assert run_result['returncode'] == 0

      return Result(time=run_result['time'])

We can actually display the result of running opentuner(the optimal block size for our multiplication problem) by creating a method, save_final_config() in our class. This saves a json dictionary of the optimal blockSize parameter found to the file mmm_final_config.json

    def save_final_config(self, configuration):
      """called at the end of tuning"""
      print "Optimal block size written to mmm_final_config.json:", configuration.data
      self.manipulator().save_to_file(configuration.data,
                                      'mmm_final_config.json')

    if __name__ == '__main__':
      argparser = opentuner.default_argparser()
      GccFlagsTuner.main(argparser.parse_args())

Generating and Viewing Results
------------------------------

Run the following command to autotune our program(The --no-dups flag hides warnings about duplicate results and the --stop-after parameter specifies that we are running opentuner for a maximum of 30 seconds):

    python mmm_tuner.py --no-dups --stop-after=30

The results of each run configuration will be displayed as follows(output lines are truncated for readability here):

    [    10s]    INFO opentuner.search.plugin.DisplayPlugin: tests=10, best {'BLOCK_SIZE': 4}, cost time=0.0081, found by DifferentialEvolutionAlt[...]
    [    19s]    INFO opentuner.search.metatechniques: AUCBanditMetaTechniqueA: [('DifferentialEvolutionAlt', 477), ('UniformGreedyMutation', 18), ('NormalGreedyMutation', 5), ('RandomNelderMead', 1)]
    [    20s]    INFO opentuner.search.plugin.DisplayPlugin: tests=10, best {'BLOCK_SIZE': 4}, cost time=0.0081, found by DifferentialEvolutionAlt[...]
    [    30s]    INFO opentuner.search.plugin.DisplayPlugin: tests=10, best {'BLOCK_SIZE': 4}, cost time=0.0081, found by DifferentialEvolutionAlt[...]
    [    30s]    INFO opentuner.search.plugin.DisplayPlugin: tests=10, best {'BLOCK_SIZE': 4}, cost time=0.0081, found by DifferentialEvolutionAlt[...]
    Optimal block size written to mmm_final_config.json: {'BLOCK_SIZE': 4}


Look up the optimal BlockSize value by inspecting the following created file:

    mmm_final_config.json

In this example, the output file content was as follows:

    {'BLOCK_SIZE': 4}
