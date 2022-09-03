import click
import os
import sys
import logging
import subprocess
import random
import psutil
import pandas

from bcc import BPF
from bcc.utils import printb
from time import sleep
from tabulate import tabulate

logger = logging.getLogger(__name__)


class benchmark:
    def __init__(
        self,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        self._workload_path = workload_path
        self._thread_count = thread_count
        self._duration_s = duration_s
        self._result = None

    @property
    def workload_type(self) -> str:
        raise NotImplementedError

    def run(self) -> None:
        result = subprocess.run(
            [
                self._workload_path,
                str(self._thread_count),
                str(self._duration_s),
                self.workload_type,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
        )

        output = result.stdout.decode("utf-8")
        self._result = float(output.split(" ")[0])

    @property
    def result(self) -> float:
        if self._result is None:
            raise AssertionError
        return self._result

    def __del__(self):
        pass


class kernel_benchmark(benchmark):
    def __init__(
        self,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        benchmark.__init__(self, workload_path, thread_count, duration_s)

        if os.getuid() != 0:
            click.echo(
                click.style("⚡ This benchmark must be executed as root", bold=True)
            )
            sys.exit(1)

        # Load benchmark modules
        subprocess.run(
            "modprobe lttng-bench".split(" "),
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    @property
    def workload_type(self) -> str:
        return "kernel"

    def __del__(self):
        benchmark.__del__(self)
        # FIXME: something (ebpf program?) appears to hold a reference to
        # the lttng-bench module, preventing its unloading.
        # skip it as it doesn't change the benchmark results anyhow.
        # subprocess.run(
        #    "rmmod lttng-bench".split(" "),
        #    check=True,
        #    stdout=sys.stdout,
        #    stderr=sys.stderr,
        # )


class ebpf_map_benchmark(kernel_benchmark):
    def __init__(
        self,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        kernel_benchmark.__init__(self, workload_path, thread_count, duration_s)

        src = """
        BPF_PERCPU_ARRAY(test_map, u64, 1024);

        int my_func(void *ctx) {
            test_map.increment(0, 1);
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
        for val in self._program["test_map"][0]:
            table.append([i, val])
            i = i + 1

        print(tabulate(table, headers=["CPU ID", "Value"]))

    def __del__(self):
        self._program.detach_tracepoint(tp="lttng_bench:lttng_bench_event")
        del self._program
        kernel_benchmark.__del__(self)


class lttng_benchmark:
    def __init__(
        self,
        lttng_bin_install_path: str,
    ):
        self._lttng_install_path = lttng_bin_install_path
        self._session_name = "session_" + self._random_string(8)
        self._channel_name = "channel_" + self._random_string(8)
        self._map_name = "map_" + self._random_string(8)
        self._trigger_name = "trigger_" + self._random_string(8)

        self._run_lttng_bin_cmd("lttng-sessiond", "-d")

    @staticmethod
    def _random_string(length: int) -> str:
        return "".join(chr(random.randrange(65, 90)) for i in range(length))

    def _run_lttng_bin_cmd(self, binary_name: str, cmd_args: str) -> None:
        if len(self._lttng_install_path) > 0:
            if not self._lttng_install_path.endswith("/"):
                bin_path = self._lttng_install_path + "/{binary_name} "
            else:
                bin_path = self._lttng_install_path + "{binary_name} "
        else:
            bin_path = "{binary_name} "

        cmd = bin_path.format(binary_name=binary_name) + cmd_args
        subprocess.run(
            cmd.split(" "), check=True, stdout=subprocess.DEVNULL, stderr=sys.stderr
        )

    def _run_lttng_cmd(self, cmd_args: str) -> None:
        self._run_lttng_bin_cmd("lttng", cmd_args)

    def view(self):
        pass

    @staticmethod
    def process_exists(name: str) -> bool:
        for process in psutil.process_iter(["name", "cmdline"]):
            if (
                process.info["name"] == name
                or process.info["cmdline"]
                and process.info["cmdline"][0] == name
            ):
                return True
        return False

    def __del__(self):
        subprocess.run(
            "killall lttng-sessiond".split(" "),
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        # wait for sessiond to die
        while self.process_exists("lttng-sessiond"):
            pass


class lttng_kernel_benchmark(kernel_benchmark, lttng_benchmark):
    def __init__(
        self,
        lttng_bin_install_path: str,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        kernel_benchmark.__init__(self, workload_path, thread_count, duration_s)
        lttng_benchmark.__init__(self, lttng_bin_install_path)

        # Load benchmark probe
        subprocess.run("modprobe lttng-bench-tp".split(" "), check=True)

    def __del__(self):
        kernel_benchmark.__del__(self)
        lttng_benchmark.__del__(self)
        subprocess.run("rmmod lttng-bench-tp".split(" "), check=True)

        # Workaround: remove sticky modules
        result = subprocess.run("lsmod", check=True, stdout=subprocess.PIPE)
        lsmod_list = result.stdout.decode("utf-8")
        for line in lsmod_list.split("\n"):
            module_name = line.split(" ")[0]
            if "lttng" in module_name:
                subprocess.run(["rmmod", module_name], check=False)


class lttng_kernel_ringbuffer_benchmark(lttng_kernel_benchmark):
    def __init__(
        self,
        lttng_bin_install_path: str,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        lttng_kernel_benchmark.__init__(
            self,
            lttng_bin_install_path,
            workload_path,
            thread_count,
            duration_s,
        )

        self._run_lttng_cmd(
            "create {session_name} --snapshot".format(session_name=self._session_name)
        )
        self._run_lttng_cmd(
            "enable-channel --session {session_name} --kernel --subbuf-size=1M --num-subbuf=4 {channel_name}".format(
                session_name=self._session_name, channel_name=self._channel_name
            )
        )
        self._run_lttng_cmd(
            "enable-event --kernel --channel {channel_name} lttng_bench_event".format(
                session_name=self._session_name,
                channel_name=self._channel_name,
            )
        )
        self._run_lttng_cmd(
            "start {session_name}".format(session_name=self._session_name)
        )

    def __del__(self):
        self._run_lttng_cmd("destroy " + self._session_name)
        lttng_kernel_benchmark.__del__(self)


class lttng_kernel_map_benchmark(lttng_kernel_benchmark):
    def __init__(
        self,
        lttng_bin_install_path: str,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        lttng_kernel_benchmark.__init__(
            self,
            lttng_bin_install_path,
            workload_path,
            thread_count,
            duration_s,
        )

        self._run_lttng_cmd(
            "create {session_name} --snapshot".format(session_name=self._session_name)
        )
        self._run_lttng_cmd(
            "add-map --session {session_name} --kernel --bitness=64 --max-key-count=1024 {map_name}".format(
                session_name=self._session_name, map_name=self._map_name
            )
        )
        self._run_lttng_cmd(
            "add-trigger --name {trigger_name} --condition event-rule-matches --type kernel:tracepoint --name lttng_bench_event --action incr-value --session {session_name} --map {map_name} --key bench_key".format(
                trigger_name=self._trigger_name,
                session_name=self._session_name,
                map_name=self._map_name,
            )
        )
        self._run_lttng_cmd(
            "start {session_name}".format(session_name=self._session_name)
        )
        # self._run_lttng_cmd(
        #    "list {session_name}".format(session_name=self._session_name)
        # )
        # self._run_lttng_cmd("list-triggers")

    def view(self) -> None:
        self._run_lttng_cmd("view-map " + self._map_name)

    def __del__(self):
        self._run_lttng_cmd("destroy " + self._session_name)
        self._run_lttng_cmd(
            "remove-trigger {trigger_name}".format(trigger_name=self._trigger_name)
        )
        lttng_kernel_benchmark.__del__(self)


class userspace_benchmark(benchmark):
    def __init__(
        self,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        benchmark.__init__(self, workload_path, thread_count, duration_s)

    @property
    def workload_type(self) -> str:
        return "ust"

    def __del__(self):
        benchmark.__del__(self)


class lttng_ust_benchmark(userspace_benchmark, lttng_benchmark):
    def __init__(
        self,
        lttng_bin_install_path: str,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        userspace_benchmark.__init__(self, workload_path, thread_count, duration_s)
        lttng_benchmark.__init__(self, lttng_bin_install_path)

    def __del__(self):
        userspace_benchmark.__del__(self)
        lttng_benchmark.__del__(self)


class lttng_ust_ringbuffer_benchmark(lttng_ust_benchmark):
    def __init__(
        self,
        lttng_bin_install_path: str,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        lttng_ust_benchmark.__init__(
            self,
            lttng_bin_install_path,
            workload_path,
            thread_count,
            duration_s,
        )

        self._run_lttng_cmd(
            "create {session_name} --snapshot".format(session_name=self._session_name)
        )
        self._run_lttng_cmd(
            "enable-channel --session {session_name} --userspace --buffers-uid --subbuf-size=1M --num-subbuf=4 {channel_name}".format(
                session_name=self._session_name, channel_name=self._channel_name
            )
        )
        self._run_lttng_cmd(
            "enable-event --userspace --channel {channel_name} lc2022:benchmark_event".format(
                session_name=self._session_name,
                channel_name=self._channel_name,
            )
        )
        self._run_lttng_cmd(
            "start {session_name}".format(session_name=self._session_name)
        )

    def __del__(self):
        self._run_lttng_cmd("destroy " + self._session_name)
        lttng_ust_benchmark.__del__(self)


class lttng_ust_map_benchmark(lttng_ust_benchmark):
    def __init__(
        self,
        lttng_bin_install_path: str,
        workload_path: str,
        thread_count: int,
        duration_s: int,
    ):
        lttng_ust_benchmark.__init__(
            self,
            lttng_bin_install_path,
            workload_path,
            thread_count,
            duration_s,
        )

        self._run_lttng_cmd(
            "create {session_name} --snapshot".format(session_name=self._session_name)
        )
        self._run_lttng_cmd(
            "add-map --session {session_name} --userspace --per-uid --bitness=64 --max-key-count=1024 {map_name}".format(
                session_name=self._session_name, map_name=self._map_name
            )
        )
        self._run_lttng_cmd(
            "add-trigger --name {trigger_name} --condition event-rule-matches --type user:tracepoint --name lc2022:benchmark_event --action incr-value --session {session_name} --map {map_name} --key bench_key".format(
                trigger_name=self._trigger_name,
                session_name=self._session_name,
                map_name=self._map_name,
            )
        )
        self._run_lttng_cmd(
            "start {session_name}".format(session_name=self._session_name)
        )

    def view(self) -> None:
        self._run_lttng_cmd("view-map " + self._map_name)

    def __del__(self):
        self._run_lttng_cmd("destroy " + self._session_name)
        self._run_lttng_cmd(
            "remove-trigger {trigger_name}".format(trigger_name=self._trigger_name)
        )
        lttng_ust_benchmark.__del__(self)


class benchmark_data:
    def __init__(self):
        self._data = []

    def add(self, point: float):
        self._data.append(point)

    def summarize(self) -> None:
        print("Time per event (ns)")
        print("-------------------")
        print("Points: " + str(self._data))
        print(pandas.Series(self._data).describe())


@click.group()
@click.option("-d", "--debug", is_flag=True, help="Set logging level to DEBUG")
@click.option("-w", "--workload", help="Workload binary path", required=True)
@click.option("--lttng-binary-path", help="LTTng binary install path", default="")
@click.option(
    "--duration",
    default=10,
    show_default=True,
    help="Duration (in seconds) during which the benchmark must run per iteration",
    metavar="DURATION",
)
@click.option(
    "--iteration-count",
    default=10,
    show_default=True,
    help="Number of iterations of the benchmark to run",
    metavar="ITERATION_COUNT",
)
@click.option(
    "--thread-count",
    default=os.cpu_count(),
    show_default=True,
    help="Number of threads to use during workload",
    metavar="THREAD_COUNT",
)
@click.pass_context
def cli(
    ctx: click.Context,
    debug: bool,
    workload: str,
    duration: int,
    iteration_count: int,
    thread_count: int,
    lttng_binary_path: str,
) -> None:
    """
    bench can run a number of benchmarks presented as part of my talk given at
    OSS Summit Europe 2022.

    LTTng: Beyond Ring-Buffer Based Tracing.

    Use --help on any of the commands for more information on their role and options.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    ctx.ensure_object(dict)
    ctx.obj["workload_path"] = workload
    ctx.obj["duration_s"] = duration
    ctx.obj["thread_count"] = thread_count
    ctx.obj["iteration_count"] = iteration_count
    ctx.obj["lttng_binary_path"] = lttng_binary_path


@cli.command(
    name="ebpf-map",
    short_help="Trace to an eBPF per-CPU array and estimate the per-event overhead",
)
@click.pass_context
def run_ebpf_map_benchmark(ctx: click.Context):
    data = benchmark_data()

    with click.progressbar(range(ctx.obj["iteration_count"])) as bar_wrapper:
        for i in bar_wrapper:
            benchmark = ebpf_map_benchmark(
                ctx.obj["workload_path"],
                ctx.obj["thread_count"],
                ctx.obj["duration_s"],
            )

            benchmark.run()
            data.add(benchmark.result)
            del benchmark

    data.summarize()


@cli.command(
    name="lttng-kernel-map",
    short_help="Trace to an LTTng-modules per-CPU map and estimate the per-event overhead",
)
@click.pass_context
def run_lttng_kernel_map_benchmark(ctx: click.Context):
    data = benchmark_data()

    with click.progressbar(range(ctx.obj["iteration_count"])) as bar_wrapper:
        for i in bar_wrapper:
            benchmark = lttng_kernel_map_benchmark(
                ctx.obj["lttng_binary_path"],
                ctx.obj["workload_path"],
                ctx.obj["thread_count"],
                ctx.obj["duration_s"],
            )

            benchmark.run()
            data.add(benchmark.result)
            del benchmark

    data.summarize()


@cli.command(
    name="lttng-kernel-ringbuffer",
    short_help="Trace to an LTTng-modules per-CPU ring-buffer and estimate the per-event overhead",
)
@click.pass_context
def run_lttng_kernel_ringbuffer_benchmark(ctx: click.Context):
    data = benchmark_data()

    with click.progressbar(range(ctx.obj["iteration_count"])) as bar_wrapper:
        for i in bar_wrapper:
            benchmark = lttng_kernel_ringbuffer_benchmark(
                ctx.obj["lttng_binary_path"],
                ctx.obj["workload_path"],
                ctx.obj["thread_count"],
                ctx.obj["duration_s"],
            )

            benchmark.run()
            data.add(benchmark.result)
            del benchmark

    data.summarize()


@cli.command(
    name="lttng-ust-map",
    short_help="Trace to an LTTng-UST per-CPU map and estimate the per-event overhead",
)
@click.pass_context
def run_lttng_ust_map_benchmark(ctx: click.Context):
    data = benchmark_data()

    with click.progressbar(range(ctx.obj["iteration_count"])) as bar_wrapper:
        for i in bar_wrapper:
            benchmark = lttng_ust_map_benchmark(
                ctx.obj["lttng_binary_path"],
                ctx.obj["workload_path"],
                ctx.obj["thread_count"],
                ctx.obj["duration_s"],
            )
            benchmark.run()
            data.add(benchmark.result)
            del benchmark

    data.summarize()


@cli.command(
    name="lttng-ust-ringbuffer",
    short_help="Trace to an LTTng-UST per-CPU ring-buffer and estimate the per-event overhead",
)
@click.pass_context
def run_lttng_ust_ringbuffer_benchmark(ctx: click.Context):
    data = benchmark_data()

    with click.progressbar(range(ctx.obj["iteration_count"])) as bar_wrapper:
        for i in bar_wrapper:
            benchmark = lttng_ust_ringbuffer_benchmark(
                ctx.obj["lttng_binary_path"],
                ctx.obj["workload_path"],
                ctx.obj["thread_count"],
                ctx.obj["duration_s"],
            )

            benchmark.run()
            data.add(benchmark.result)
            del benchmark

    data.summarize()
