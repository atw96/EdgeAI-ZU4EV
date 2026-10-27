#define _GNU_SOURCE
#include <dlfcn.h>
#include <time.h>
#include <sys/time.h>

/* Vivado 2020.1 stores IP core_revision as a signed 32-bit YYMMDDHHMM.
   Dates from 2022 onward overflow. Freeze CLOCK_REALTIME at 2020-09-13. */
static const time_t FAKE = 1600000000;

int clock_gettime(clockid_t clk_id, struct timespec *tp) {
    static int (*real_clock_gettime)(clockid_t, struct timespec *) = 0;
    if (!real_clock_gettime)
        real_clock_gettime = dlsym(RTLD_NEXT, "clock_gettime");
    int rc = real_clock_gettime(clk_id, tp);
    if (tp && clk_id == CLOCK_REALTIME) {
        tp->tv_sec = FAKE;
        tp->tv_nsec = 0;
    }
    return rc;
}

time_t time(time_t *tloc) {
    if (tloc)
        *tloc = FAKE;
    return FAKE;
}

int gettimeofday(struct timeval *tv, struct timezone *tz) {
    (void)tz;
    if (tv) {
        tv->tv_sec = FAKE;
        tv->tv_usec = 0;
    }
    return 0;
}
