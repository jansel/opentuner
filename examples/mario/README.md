## Dependencies

- FCEUX, a NES emulator
- Super Mario Bros., assumed to be named `smb.nes`, which we can't help you get for legal reasons

## Running

Run the tuner with `./smb-opentuner.py --technique=PSO_GA_Bandit`; it will launch FCEUX to run trials.  You can experiment with other techniques or `--parallelism` too.

You can implement your own configuration representation by subclassing Representation and passing `--representation=YourRepresentation`.  Your Representation class needs to provide a ConfigurationManipulator populated with parameters and a method to translate these parameters to button presses.

You can implement your own fitness function by subclassing FitnessFunction and passing `--fitness-function=YourFunction`.  Your function receives a win/loss boolean, the number of pixels moved to the right when the trial ended, and the number of frames that elapsed during the trial.  Lower fitness scores are better.

Once you've finished a tuning run, you can get its id from the database and run `./smb-opentuner.py --tuning-run=N > tuning-run-N.fm2` to generate a movie file of each new-best configuration concatenated together for convenient viewing.

## TODO

- use the [fm2 format](http://www.fceux.com/web/help/fceux.html?fm2.html)'s subtitle support in new-bests movies to show run number and fitness score

## Links

- [Videos showing OpenTuner player Super Mario Bros](https://www.youtube.com/playlist?list=PLngnz1zPEA08FWy8wF9JbGqjlm-elHmlb)
- [Slides describing representation and results](http://groups.csail.mit.edu/commit/papers/2014/ansel-pact14-opentuner-slides.pdf) (see slide 16)

