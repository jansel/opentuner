#include <Halide.h>
#include <stdio.h>
#include <sys/time.h>
#include <unistd.h>

#include <map>
#include <string>

// How many times to run (and take min)
// #define AUTOTUNE_TRIALS 3

// Limit in seconds to try running for (0 = no limit)
// #define AUTOTUNE_LIMIT 0

// Size to run with
// #define AUTOTUNE_N 1024, 1024

inline void _autotune_timing_stub(Halide::Func& func) {
    func.compile_jit();

    // TODO: this assumes scalar/non-Tuple outputs - should generalize to a Realization
    std::vector<Halide::Type> out_types = func.output_types();
    std::vector<buffer_t> out_raw_bufs;
    std::vector<Halide::Buffer> out_bufs;

    for (int i = 0; i < out_types.size(); i++) {
    // Use the Buffer constructor as a helper to set up the buffer_t,
    // but then throw away its allocation which we don't really want.
        Halide::Buffer bufinit(out_types[i], AUTOTUNE_N);
        out_raw_bufs.push_back(*bufinit.raw_buffer());
        out_raw_bufs[i].host = NULL;
        out_bufs.push_back(Halide::Buffer(out_types[i], &out_raw_bufs[i]));
        assert(out_bufs[i].host_ptr() == NULL); // make sure we don't have an allocation
    }
    Halide::Realization output(out_bufs);
    func.infer_input_bounds(output, 5);
    assert(output[0].host_ptr());

    timeval t1, t2;
    double rv = 0;
    const unsigned int timeout = AUTOTUNE_LIMIT;
    alarm(timeout);
    for (int i = 0; i < AUTOTUNE_TRIALS; i++) {
      gettimeofday(&t1, NULL);
      func.realize(output);
      gettimeofday(&t2, NULL);
      alarm(0); // disable alarm
      double t = (t2.tv_sec - t1.tv_sec) + (t2.tv_usec - t1.tv_usec)/1000000.0;
      if(i == 0 || t < rv)
        rv = t;
    }
    printf("{\"time\": %.10f}\n", rv);
    exit(0);
}


#ifndef AUTOTUNE_HOOK
#define AUTOTUNE_HOOK(x)
#endif

#ifndef BASELINE_HOOK
#define BASELINE_HOOK(x)
#endif

