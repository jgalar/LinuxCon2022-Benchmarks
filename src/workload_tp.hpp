/*
 * Copyright (C) 2022 Jérémie Galarneau <jeremie.galarneau@efficios.com>
 *
 * SPDX-License-Identifier: LGPL-2.1-only
 *
 */

#undef LTTNG_UST_TRACEPOINT_PROVIDER
#define LTTNG_UST_TRACEPOINT_PROVIDER lc2022

#if !defined(_TRACEPOINT_LC22_WORKLOAD_TP_H) || defined(LTTNG_UST_TRACEPOINT_HEADER_MULTI_READ)
#define _TRACEPOINT_LC22_WORKLOAD_TP_H

#include <lttng/tracepoint.h>
#include <stddef.h>

LTTNG_UST_TRACEPOINT_EVENT(lc2022, benchmark_event,
	LTTNG_UST_TP_ARGS(unsigned int, anint),
	LTTNG_UST_TP_FIELDS(
		lttng_ust_field_integer(unsigned int, intfield, anint)
	)
)

#endif /* _TRACEPOINT_LC22_WORKLOAD_TP_H */

#undef LTTNG_UST_TRACEPOINT_INCLUDE
#define LTTNG_UST_TRACEPOINT_INCLUDE "./workload_tp.hpp"

/* This part must be outside ifdef protection */
#include <lttng/tracepoint-event.h>