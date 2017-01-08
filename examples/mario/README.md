This is an OpenTuner-based tuner that learns a series of button presses that complete the first level of Super Mario Bros. for the original Nintendo Entertainment System.

## Dependencies

- FCEUX, a NES emulator
- `xvfb-run`, to run the emulator headless (optional, but speeds up tuning)
- Super Mario Bros., assumed to be named `smb.nes`, which we can't help you get for legal reasons

## Running

Run the tuner with `./mario.py --technique=PSO_GA_Bandit`; it will launch FCEUX to run trials.  You can experiment with other techniques or `--parallelism` (the number of trials to run in parallel) too.

You can implement your own configuration representation by subclassing Representation and passing `--representation=YourRepresentation`.  Your Representation class needs to provide a ConfigurationManipulator populated with parameters and a method to translate these parameters to button presses.  There are already a few representations implemented to use as examples.

You can implement your own fitness function by subclassing FitnessFunction and passing `--fitness-function=YourFunction`.  Your function receives a win/loss boolean, the number of pixels moved to the right when the trial ended, and the number of frames that elapsed during the trial.  Lower fitness scores are better.  There are a few existing fitness functions; in particular, `ProgressTimesAverageSpeed` also tries to optimize speed.

If you want to watch the trials (or don't have `xvfb-run` available), pass `--headful`.

## Playing the results

When a tuning run completes, the best configuration (as judged by the fitness function) is written to `<hostname>-<tuningrun>.fm2`.  This file can be played back in FCEUX to watch the best configuration.

You can also use the `--tuning-run=` option (passing the tuning run number in the best configuration `.fm2`) to generate a new-bests `.fm2`, which will contain each tuning trial that was the best configuration found so far during the tuning run, concatenated back-to-back.  You also need to pass `--database` pointing to the database containing that tuning run, and if you passed `--representation` or `--fitness-function` during the tuning run, you need to pass the same values for those parameters.  So your final command might look like `./mario.py --tuning-run=42 --database=opentuner.db/hostname.db --representation=NaiveRepresentation --fitness-function=ProgressTimesAverageSpeed > new-bests-42.fm2`.

## TODO

- use the [fm2 format](http://www.fceux.com/web/help/fceux.html?fm2.html)'s subtitle support in new-bests movies to show run number and fitness score

## Links

- [Videos showing OpenTuner playing Super Mario Bros](https://www.youtube.com/playlist?list=PLngnz1zPEA08FWy8wF9JbGqjlm-elHmlb)
- [Slides describing representation and results](http://groups.csail.mit.edu/commit/papers/2014/ansel-pact14-opentuner-slides.pdf) (see slide 16)

