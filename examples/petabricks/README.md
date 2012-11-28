Source for PetaBricks binaries can be found at:
  - https://github.com/petabricks/petabricks/
  - https://code.google.com/p/petabricks/


Basic usage for running the raw programs is:
```
./Prog --config=CONFIG -n=N --time --accuracy --max-sec=TIMEOUT --trials=1

--config=<STRING>
    filename of the program configuration (see example in .cfg.default file)
--n=<INTEGER>
    generate a random input of the given size and run it
--time
    print timing results in xml format
--accuracy
    print out accuracy of answer
--max-sec=<NUMBER> (default: 1.79769e+308)
    terminate measurement if it exceeds the given number of seconds

many more options are given by running ./Prog --help
```


