Tutorial: Optimizing Block Matrix Multiplication
================================================

This tutorial assumes that you have checked out a copy of opentuner. For information on how to do this, refer [here][technique-tutorial]

[technique-tutorial]: http://opentuner.org/tutorial/setup

Identifying a Program to Autotune
---------------------------------

In order to do autotuning, you first need something to autotune. This will normally be your own program that you want to make either fast or better in some way.  For this tutorial we will use a blocked version
of matrix multiply as an example. We will use opentuner to find the optimal value of the block size parameter.

We will autotone the sample code below(based off of modification of code found here), making sure to take the block size as a command line input to the program. 

Save the sample code below to examples/gccflags/apps/mmm_block.cpp

    #include <stdio.h>
    #include <cstdlib>

    int main(int argc, const char** argv)
    {
      int BlockSize = atoi(argv[1])*5;
      int n = BlockSize * (n/BlockSize);
      int a[100][100];
      int b[100][100];
      int c[100][100];
      int sum=0;
      for(int k1=0;k1<n;k1+=BlockSize)
      {
          for(int j1=0;j1<n;j1+=BlockSize)
          {
              for(int k1=0;k1<n;k1+=BlockSize)
              {
                  for(int i=0;i<n;i++)
                  {
                      for(int j=j1;j<j1+BlockSize;j++)
                      {
                          sum = c[i][j];
                          for(int k=k1;k<k1+BlockSize;k++)
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

Save the following code to examples/gccflags/mmm_tuner.py

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

        gcc_cmd = 'g++ apps/mmm_block.cpp -DBLOCK_SIZE=5 -o ./tmp.bin'   

        compile_result = self.call_program(gcc_cmd)
        assert compile_result['returncode'] == 0

        run_cmd = './tmp.bin'
        run_cmd += ' {0}'.format(cfg['blockSize'])
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

      gcc_cmd = 'g++ apps/mmm_block.cpp -DBLOCK_SIZE=5 -o ./tmp.bin'  

      compile_result = self.call_program(gcc_cmd)
      assert compile_result['returncode'] == 0

      run_cmd = './tmp.bin'
      run_cmd += ' {0}'.format(cfg['blockSize'])
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

Run the following command to autotune our program(The --no-dups option hides warnings about duplicate results):
    
    python mmm_tuner.py --no-dups

The results of each run configuration will be displayed, and will look similar to:
    
    [     5s]    INFO opentuner.search.metatechniques: AUCBanditMetaTechniqueA: [('NormalGreedyMutation', 484), ('UniformGreedyMutation', 12), ('DifferentialEvolutionAlt', 4), ('RandomNelderMead', 1)]
    [     8s]    INFO opentuner.search.metatechniques: AUCBanditMetaTechniqueA: [('NormalGreedyMutation', 489), ('UniformGreedyMutation', 8), ('DifferentialEvolutionAlt', 4)]
    [    10s]    INFO opentuner.search.plugin.DisplayPlugin: tests=10, best {'blockSize': 5}, cost time=0.0082, found by UniformGreedyMutation
    [    13s]    INFO opentuner.search.metatechniques: AUCBanditMetaTechniqueA: [('NormalGreedyMutation', 445), ('DifferentialEvolutionAlt', 48), ('UniformGreedyMutation', 8)]
    [    20s]    INFO opentuner.search.plugin.DisplayPlugin: tests=10, best {'blockSize': 5}, cost time=0.0082, found by UniformGreedyMutation,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt,DifferentialEvolutionAlt
    [    21s]    INFO opentuner.search.metatechniques: AUCBanditMetaTechniqueA: [('NormalGreedyMutation', 357), ('DifferentialEvolutionAlt', 140), ('UniformGreedyMutation', 4)]


Look up the optimal BlockSize value by inspecting the following created file:
    
    mmm_final_config.json

In this example, the output file content was as follows:

    {"blockSize": 5}
