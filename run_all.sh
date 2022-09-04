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

        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-ust-ringbuffer --num-subbuf 4 --subbuf-size 8M
        poetry run bench --workload build/workload --duration $DURATION --iteration-count $ITER_COUNT lttng-kernel-ringbuffer --num-subbuf 4 --subbuf-size 8M

        echo "Machine summary"
        echo "---------------"
        echo ""
        echo "cpu info"
        echo "--------"
        cat /proc/cpuinfo
        echo ""
        echo "mem info"
        echo "--------"
        cat /proc/meminfo
        echo ""
        echo "numa info"
        echo "---------"
        numactl --hardware
        echo ""
        echo "kernel:"
        echo "-------"
        uname -a
        echo ""
        echo "distro info:"
        echo "------------"
        lsb_release -a
        echo ""
        echo "kernel cfg:"
        echo "-----------"
        zcat /proc/config.gz
        cat "/boot/config-$(uname -r)"
        echo ""
        echo "lshw:"
        echo "-----------"
        lshw
} > results