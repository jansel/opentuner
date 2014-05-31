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
        // TODO: free the host pointer?!
        out_bufs.push_back(Halide::Buffer(out_types[i], &out_raw_bufs[i]));
        assert(out_bufs[i].host_ptr() == NULL); // make sure we don't have an allocation
    }
    Halide::Realization output(out_bufs);
    func.infer_input_bounds(output);
    // assert(output[0].host_ptr()); // for now, the API doesn't seem to allocate outputs
    
    // TODO: this should go into Func::infer_input_bounds(Realization)
    for (int i = 0; i < output.size(); i++) {
        assert(!output[i].host_ptr()); // for now, the API doesn't seem to allocate outputs
        buffer_t buf = *output[i].raw_buffer();
        
        // Figure out how much memory to allocate for this buffer
        size_t min_idx = 0, max_idx = 0;
        for (int d = 0; d < 4; d++) {
            if (buf.stride[d] > 0) {
                min_idx += buf.min[d] * buf.stride[d];
                max_idx += (buf.min[d] + buf.extent[d] - 1) * buf.stride[d];
            } else {
                max_idx += buf.min[d] * buf.stride[d];
                min_idx += (buf.min[d] + buf.extent[d] - 1) * buf.stride[d];
            }
        }
        size_t total_size = (max_idx - min_idx);
        while (total_size & 0x1f) total_size++;

        // Allocate enough memory with the right dimensionality.
        Halide::Buffer buffer(output[i].type(), total_size,
                      buf.extent[1] > 0 ? 1 : 0,
                      buf.extent[2] > 0 ? 1 : 0,
                      buf.extent[3] > 0 ? 1 : 0);

        // Rewrite the buffer fields to match the ones returned
        for (int d = 0; d < 4; d++) {
            buffer.raw_buffer()->min[d] = buf.min[d];
            buffer.raw_buffer()->stride[d] = buf.stride[d];
            buffer.raw_buffer()->extent[d] = buf.extent[d];
        }
        
        output[i] = buffer;
    }

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

