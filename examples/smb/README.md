## Dependencies

- [OpenTuner](https://github.com/jansel/opentuner), assumed to be checked out in `../opentuner`
- FCEUX, a NES emulator
- Super Mario Bros., assumed to be named `smb.nes`, which we can't help you get for legal reasons

## Running

Run the tuner with `./smb-opentuner.py --technique=PSO_GA_Bandit`; it will launch FCEUX to run trials.  You can experiment with other techniques too.

Once you've finished a tuning run, you can get its id from the database and run `./smb-opentuner.py --tuning-run=N > tuning-run-N.fm2` to generate a movie file of each new-best configuration concatenated together for convenient viewing.

## TODO

- build a headless FCEUX, or find another NES emulator supporting the standard emulator Lua APIs
- parallel trials (OpenTuner's `--parallelism` option), which does not seem to work right now (still only runs one trial at a time)
- use the [fm2 format](http://www.fceux.com/web/help/fceux.html?fm2.html)'s subtitle support in new-bests movies to show run number and fitness score
