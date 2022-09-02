# Setup

```sh
# Install bcc, see https://github.com/iovisor/bcc/blob/master/INSTALL.md

# Build workload
$ mkdir build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make && cd ..

Personally, I typically work on development versions of LTTng that are not
installed system-wide.

In those cases, passing `-DCMAKE_PREFIX_PATH=~/your/custom/install/prefix/` can
be useful.

# Setup python virtual env with poetry
$ poetry install
```

# Running benchmarks

The `bench` util runs the various benchmark scenarios.

```
Usage: bench [OPTIONS] COMMAND [ARGS]...

  bench can run a number of benchmarks presented as part of my talk given at
  OSS Summit Europe 2022.

  LTTng: Beyond Ring-Buffer Based Tracing.

  Use --help on any of the commands for more information on their role and
  options.

Options:
  -d, --debug                     Set logging level to DEBUG
  -w, --workload TEXT             Workload binary path  [required]
  --lttng-binary-path TEXT        LTTng binary install path  [required]
  --duration DURATION             Duration (in seconds) during which the
                                  benchmark must run per iteration  [default:
                                  10]
  --iteration-count ITERATION_COUNT
                                  Number of iterations of the benchmark to run
                                  [default: 10]
  --thread-count THREAD_COUNT     Number of threads to use during workload
                                  [default: number of cpus on the system]
  --help                          Show this message and exit.

Commands:
  ebpf-map                 Trace to an eBPF per-CPU array and estimate the
                           per-event overhead
  lttng-kernel-map         Trace to an LTTng-modules per-CPU map and estimate
                           the per-event overhead
  lttng-kernel-ringbuffer  Trace to an LTTng-modules per-CPU ring-buffer and
                           estimate the per-event overhead
  lttng-ust-map            Trace to an LTTng-UST per-CPU map and estimate the
                           per-event overhead
  lttng-ust-ringbuffer     Trace to an LTTng-UST per-CPU ring-buffer and
                           estimate the per-event overhead
```

Here's an example of using `bench` to run the `lttng-ust-map` scenario.
```sh
# Setup the python virtual environment
$ poetry shell
# Run the benchmark
# Note that workload points to the workload binary we built earlier
$ bench --workload build/workload --iteration-count 10 --duration 10 --thread-count $(nproc) lttng-ust-map
```