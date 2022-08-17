import click
import os
import sys
import logging

from bcc import BPF
from bcc.utils import printb
from time import sleep
from tabulate import tabulate

logger = logging.getLogger(__name__)


class kernel_benchmark:
    def __init__(self):
        if os.getuid() != 0:
            click.echo(
                click.style("⚡ This benchmark must be executed as root", bold=True)
            )
            sys.exit(1)


class ebpf_map_benchmark(kernel_benchmark):
    def __init__(self):
        super().__init__()

        src = """
        BPF_PERCPU_ARRAY(test_map, u64, 1024);

        int my_func(void *ctx) {
            test_map.increment(511, 1);
            return 0;
        }
        """

        program = BPF(text=src)
        program.attach_tracepoint(tp="lttng_bench:lttng_bench_event", fn_name="my_func")

        # The bpf map remains persistent as long as this object exists
        self._program = program

    def view(self):
        table = []
        i = 0
        for val in self._program["test_map"][511]:
            table.append([i, val])
            i = i + 1

        print(tabulate(table, headers=["CPU ID", "Value"]))


class lttng_kernel_ringbuffer_benchmark(kernel_benchmark):
    def __init__(self, lttng_install_path: str):
        super().__init__()
        self._lttng_install_path = lttng_install_path

    def view(self):
        # call lttng view
        pass


class lttng_kernel_map_benchmark(kernel_benchmark):
    def __init__(self, lttng_install_path: str):
        super().__init__()
        self._lttng_install_path = lttng_install_path

    def view(self):
        # call lttng view
        pass


@click.group()
@click.option("-d", "--debug", is_flag=True, help="Set logging level to DEBUG")
def cli(debug: bool) -> None:
    """
    bench can run a number of benchmarks presented as part of my talk given at
    OSS Summit Europe 2022.

    LTTng: Beyond Ring-Buffer Based Tracing.

    Use --help on any of the commands for more information on their role and options.
    """
    bench = ebpf_map_benchmark()

    # Wait for benchmark to end.
    while 1:
        bench.view()
        sleep(2)


@cli.command(
    name="ebpf-map",
    short_help="Trace to an eBPF per-CPU array and estimate the per-event overhead",
)
@click.option(
    "--duration",
    default=10,
    help="Duration (in seconds) during which the benchmark must run per iteration",
    metavar="DURATION",
)
@click.option(
    "--iteration-count",
    default=10,
    help="Number of iterations of the benchmark to run",
    metavar="COUNT",
)
def run_ebpf_map_benchmark():
    pass


@cli.command(
    name="lttng-kernel-map",
    short_help="Trace to an LTTng-modules per-CPU map and estimate the per-event overhead",
)
@click.option(
    "--duration",
    default=10,
    help="Duration (in seconds) during which the benchmark must run per iteration",
    metavar="DURATION",
)
@click.option(
    "--iteration-count",
    default=10,
    help="Number of iterations of the benchmark to run",
    metavar="COUNT",
)
def run_lttng_kernel_map_benchmark():
    pass


@cli.command(
    name="lttng-kernel-ringbuffer",
    short_help="Trace to an LTTng-modules per-CPU ring-buffer and estimate the per-event overhead",
)
@click.option(
    "--duration",
    default=10,
    help="Duration (in seconds) during which the benchmark must run per iteration",
    metavar="DURATION",
)
@click.option(
    "--iteration-count",
    default=10,
    help="Number of iterations of the benchmark to run",
    metavar="COUNT",
)
def run_lttng_kernel_ringbuffer_benchmark():
    pass


@cli.command(
    name="lttng-ust-map",
    short_help="Trace to an LTTng-UST per-CPU map and estimate the per-event overhead",
)
@click.option(
    "--duration",
    default=10,
    help="Duration (in seconds) during which the benchmark must run per iteration",
    metavar="DURATION",
)
@click.option(
    "--iteration-count",
    default=10,
    help="Number of iterations of the benchmark to run",
    metavar="COUNT",
)
def run_lttng_ust_map_benchmark():
    pass


@cli.command(
    name="lttng-ust-ringbuffer",
    short_help="Trace to an LTTng-UST per-CPU ring-buffer and estimate the per-event overhead",
)
@click.option(
    "--duration",
    default=10,
    help="Duration (in seconds) during which the benchmark must run per iteration",
    metavar="DURATION",
)
@click.option(
    "--iteration-count",
    default=10,
    help="Number of iterations of the benchmark to run",
    metavar="COUNT",
)
def run_lttng_ust_ringbuffer_benchmark():
    pass
