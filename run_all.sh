#!/usr/bin/env sh
DURATION=10
ITER_COUNT=10

poetry install

{
        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT ebpf-map

        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-ust-map
        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-kernel-map

        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-ust-ringbuffer --num-subbuf 4 --subbuf-size 4K
        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-kernel-ringbuffer --num-subbuf 4 --subbuf-size 4K

        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-ust-ringbuffer --num-subbuf 4 --subbuf-size 4M
        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-kernel-ringbuffer --num-subbuf 4 --subbuf-size 4M
} > results