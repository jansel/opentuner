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
    Halide::Type out_type = func.output_types()[0];
    buffer_t out_size_buf;
    {
        // Use the Buffer constructor as a helper to set up the buffer_t,
        // but then throw away its allocation which we don't really want.
        Halide::Buffer bufinit(out_type, AUTOTUNE_N);
        out_size_buf = *bufinit.raw_buffer();
        out_size_buf.host = NULL;
    }
    Halide::Buffer out_size(out_type, &out_size_buf);
    assert(out_size.host_ptr() == NULL); // make sure we don't have an allocation

    func.infer_input_bounds(out_size);

    // allocate the real output using the inferred mins + extents
    Halide::Buffer output(  out_type,
                            out_size.extent(0),
                            out_size.extent(1),
                            out_size.extent(2),
                            out_size.extent(3),
                            NULL,
                            "output" );
    output.set_min( out_size.min(0),
                    out_size.min(1),
                    out_size.min(2),
                    out_size.min(3) );

    // re-run input inference on enlarged output buffer
    func.unbind_image_params(); // TODO: iterate to convergence
    func.infer_input_bounds(output);

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

