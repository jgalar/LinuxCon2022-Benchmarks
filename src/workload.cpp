/*
 * Copyright (C) 2022 Jérémie Galarneau <jeremie.galarneau@efficios.com>
 *
 * SPDX-License-Identifier: LGPL-2.1-only
 *
 */

#define _LGPL_SOURCE

#include <iostream>
#include <atomic>
#include <string>
#include <thread>
#include <vector>
#include <cassert>
#include <memory>

#include <poll.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/types.h>
#include <dirent.h>
#include <limits.h>
#include <pthread.h>

#include "workload_tp.hpp"

namespace {
std::atomic<unsigned int> stop_threads;
std::atomic<unsigned int> threads_ready_count;
std::atomic<unsigned int> threads_go;

int64_t timespec_delta_ns(const timespec &t1, const timespec &t2)
{
        timespec delta;

        delta.tv_sec = t2.tv_sec - t1.tv_sec;
        delta.tv_nsec = t2.tv_nsec - t1.tv_nsec;
        return ((int64_t) 1000000000 * (int64_t) delta.tv_sec) +
                        (int64_t) delta.tv_nsec;
}

timespec sample_time()
{
        timespec t;
        const auto ret = clock_gettime(CLOCK_MONOTONIC, &t);

        if (ret < 0) {
                std::cerr << "Failed to sample clock monotonic" << std::endl;
                std::abort();
        }

        return t;
}

/* Extracted from LTTng-ust common/smp.c */
int _get_max_cpuid_from_sysfs(const char *path)
{
        long max_cpuid = -1;

        DIR *cpudir;
        struct dirent *entry;

        assert(path);

        cpudir = opendir(path);
        if (cpudir == NULL)
                goto end;

        /*
         * Iterate on all directories named "cpu" followed by an integer.
         */
        while ((entry = readdir(cpudir))) {
                if (entry->d_type == DT_DIR &&
                        strncmp(entry->d_name, "cpu", 3) == 0) {

                        char *endptr;
                        long cpu_id;

                        cpu_id = strtol(entry->d_name + 3, &endptr, 10);
                        if ((cpu_id < LONG_MAX) && (endptr != entry->d_name + 3)
                                        && (*endptr == '\0')) {
                                if (cpu_id > max_cpuid)
                                        max_cpuid = cpu_id;
                        }
                }
        }

        if (closedir(cpudir)) {
                std::cerr << "Failed to close CPU directory" << std::endl;
        }

        /*
         * If the max CPU id is out of bound, set it to -1 so it results in a
         * CPU num of 0.
         */
        if (max_cpuid < 0 || max_cpuid > INT_MAX)
                max_cpuid = -1;

end:
        return max_cpuid;
}

/*
 * Get the highest CPU id from sysfs.
 *
 * Iterate on all the folders in "/sys/devices/system/cpu" that start with
 * "cpu" followed by an integer, keep the highest CPU id encountered during
 * this iteration and add 1 to get a number of CPUs.
 *
 * Returns the highest CPU id, or -1 on error.
 * 
 * Extracted from LTTng-ust common/smp.c
 */
int get_max_cpuid_from_sysfs(void)
{
        return _get_max_cpuid_from_sysfs("/sys/devices/system/cpu");
}

void set_current_thread_affinity(unsigned int cpu_id)
{
        const auto max_cpu_id = get_max_cpuid_from_sysfs();
        cpu_set_t cpu_set;

        if (max_cpu_id < 0) {
                std::cerr << "Failed to get max cpu id from sysfs" << std::endl;
                std::abort();
        }

        CPU_ZERO(&cpu_set);
        CPU_SET(cpu_id % (max_cpu_id + 1), &cpu_set);
        const auto ret = pthread_setaffinity_np(pthread_self(), sizeof(cpu_set), &cpu_set);
        if (ret < 0) {
                std::cerr << "Failed to set affinity of thread to CPU #" << cpu_id << std::endl;
                std::abort();
        }
}

void thread_workload_ust(unsigned int thread_id, uint64_t &iteration_count, int64_t &elapsed_time_ns)
{
        uint64_t count = 0;

        set_current_thread_affinity(thread_id);

        threads_ready_count++;

        while (!threads_go) {}

        const auto time_begin = sample_time();
        while (!stop_threads) {
                tracepoint(lc2022, benchmark_event, static_cast<unsigned int>(count));
                count++;
        }

        const auto time_end = sample_time();
        elapsed_time_ns = timespec_delta_ns(time_begin, time_end);
        iteration_count = count;
}

void thread_workload_kernel(unsigned int thread_id, int proc_file_fd, uint64_t &iteration_count, int64_t &elapsed_time_ns)
{
        const unsigned int batch_size = 10000;
        std::string batch_size_str{ std::to_string(batch_size) };
        uint64_t count = 0;

        set_current_thread_affinity(thread_id);

        threads_ready_count++;

        while (!threads_go) {}

        const auto time_begin = sample_time();
        while (!stop_threads) {
                const auto ret = write(proc_file_fd, batch_size_str.c_str(), batch_size_str.size() + 1);

                if (ret < 0) {
                        std::cerr << "Failed to write batch size to proc file" << std::endl;
                        std::abort();
                }

                count += batch_size;
        }

        const auto time_end = sample_time();
        elapsed_time_ns = timespec_delta_ns(time_begin, time_end);
        iteration_count = count;
}
}

int main(int argc, const char **argv)
{
        unsigned int thread_count, duration_seconds;
        std::string workload_domain;

        if (argc != 4) {
                std::cerr << "Usage: workload THREAD_COUNT DURATION_SECONDS WORKLOAD_DOMAIN" << std::endl;
                return 1;
        }

        assert(stop_threads.is_lock_free());
        assert(threads_go.is_lock_free());

        // Parse workload arguments.
        try {
                thread_count = std::stoi(argv[1]);
        } catch (const std::invalid_argument &ex) {
                std::cerr << "Invalid thread count: " << argv[1] << std::endl;
                return 1;
        }

        try {
                duration_seconds = std::stoi(argv[2]);
        } catch (const std::invalid_argument &ex) {
                std::cerr << "Invalid duration: " << argv[2] << std::endl;
                return 1;
        }

        workload_domain = argv[3];
        if (workload_domain != "kernel" && workload_domain != "ust") {
                std::cerr << "Unknown workload domain: " << workload_domain << std::endl;
                return 1;
        }

        std::vector<std::thread> threads;
        std::vector<std::uint64_t> thread_event_counters(thread_count);
        std::vector<std::int64_t> thread_elapsed_time_ns(thread_count);
        std::vector<int> thread_proc_file_fds;
        for (unsigned int thread_id = 0; thread_id < thread_count; thread_id++) {
                if (workload_domain == "kernel") {
                        auto proc_file_fd = open("/proc/lttng-bench-event", O_WRONLY);
                        if (proc_file_fd < 0) {
                                std::cerr << "Failed to open proc file" << std::endl;
                                return 1;
                        }

                        threads.emplace_back(thread_workload_kernel, thread_id, proc_file_fd,
                                std::ref(thread_event_counters[thread_id]),
                                std::ref(thread_elapsed_time_ns[thread_id]));

                        thread_proc_file_fds.push_back(proc_file_fd);
                } else {
                        threads.emplace_back(thread_workload_ust, thread_id,
                                std::ref(thread_event_counters[thread_id]),
                                std::ref(thread_elapsed_time_ns[thread_id]));
                }
        }

        while (threads_ready_count < thread_count) {}

        threads_go = 1;

        // TODO change time accounting for a runtime-per-thread approach
        // sampling the monotonic clock on begin/end of thread loops
        if (poll(nullptr, 0, duration_seconds * 1000) < 0) {
                std::cerr << "Error returned from poll" << std::endl;
                std::abort();
        }

        stop_threads = 1;

        for (auto &thread : threads) {
                thread.join();
        }

        for (const auto fd : thread_proc_file_fds) {
                if (close(fd)) {
                        std::cerr << "Failed to close proc file" << std::endl;
                }
        }

        uint64_t total_count = 0;
        for (const auto thread_counter : thread_event_counters) {
                total_count += thread_counter;
        }

        double total_run_time_s = 0.0;
        for (const auto thread_time_ns : thread_elapsed_time_ns) {
                total_run_time_s += double(thread_time_ns) / double(1000000000);
        }

        /*
         * Time per event is derived as:
         *   test_duration (seconds)
         *   -----------------------  * 1,000,000,000 (ns / s) * thread_count
         *    event_count (events)
         */
        std::cout << ((((static_cast<double>(total_run_time_s) / static_cast<double>(total_count)) * double(1000000000)))) << " ns per event" << std::endl;
        return 0;
}
