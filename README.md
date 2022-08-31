# Setup

```sh
# Install bcc, see https://github.com/iovisor/bcc/blob/master/INSTALL.md

# Build workload
$ mkdir build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=~/EfficiOS/src/LTTng-THC/usr/ && make && cd ..

# Setup python virtual env with poetry
$ poetry install
```

# Running benchmarks

```sh
# ...
```
