#define _POSIX_C_SOURCE 200809L
/* X3: IOC-to-visible delay of bytes 88-95, plus a 10 us double-read.
 * Does not touch PL0_REF_CTRL. One soft reset, then clear IOC before every start.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>

#define DMA_PHYS 0x80040000u
#define SRC_PHYS 0x66C00000u
#define DST_PHYS 0x66C02000u
#define PAGE 0x1000u
#define IN_BYTES 6144
#define OUT_BYTES 96
#define OUT_DIM 24
#define IOC 0x1000u
#define ERR_MASK 0x770u
#define MM2S_CR 0x00u
#define MM2S_SR 0x04u
#define MM2S_SA 0x18u
#define MM2S_SA_MSB 0x1Cu
#define MM2S_LEN 0x28u
#define S2MM_CR 0x30u
#define S2MM_SR 0x34u
#define S2MM_DA 0x48u
#define S2MM_DA_MSB 0x4Cu
#define S2MM_LEN 0x58u
#define SPAN 10000

static volatile uint32_t *reg;
static uint8_t *src_map;
static volatile uint8_t *dst_map;

static uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static uint32_t rd(unsigned off)
{
    return reg[off >> 2];
}

static void wr(unsigned off, uint32_t v)
{
    reg[off >> 2] = v;
}

static int pl_operating(void)
{
    char buf[64];
    FILE *fp = fopen("/sys/class/fpga_manager/fpga0/state", "r");
    if (!fp)
        return 0;
    if (!fgets(buf, sizeof buf, fp)) {
        fclose(fp);
        return 0;
    }
    fclose(fp);
    return strncmp(buf, "operating", 9) == 0;
}

static int map_all(void)
{
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    void *r, *s, *d;
    if (fd < 0)
        return -1;
    r = mmap(NULL, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, DMA_PHYS);
    s = mmap(NULL, 8192, PROT_READ | PROT_WRITE, MAP_SHARED, fd, SRC_PHYS);
    d = mmap(NULL, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, DST_PHYS);
    if (r == MAP_FAILED || s == MAP_FAILED || d == MAP_FAILED)
        return -1;
    reg = r;
    src_map = s;
    dst_map = d;
    return 0;
}

static int soft_reset(void)
{
    uint64_t deadline = now_ns() + 100000000ull;
    wr(MM2S_CR, rd(MM2S_CR) | 4u);
    wr(S2MM_CR, rd(S2MM_CR) | 4u);
    while (now_ns() < deadline) {
        if ((rd(MM2S_CR) & 4u) == 0 && (rd(S2MM_CR) & 4u) == 0)
            return 0;
    }
    fprintf(stderr, "RESET_FAIL\n");
    return -1;
}

static int ensure_idle(void)
{
    int attempt;
    for (attempt = 0; attempt < 3; attempt++) {
        uint32_t s2 = rd(S2MM_SR);
        uint32_t m2 = rd(MM2S_SR);
        if (s2 & IOC)
            wr(S2MM_SR, IOC);
        if (m2 & IOC)
            wr(MM2S_SR, IOC);
        s2 = rd(S2MM_SR);
        m2 = rd(MM2S_SR);
        if ((s2 & IOC) == 0 && (m2 & IOC) == 0 && (s2 & ERR_MASK) == 0 && (m2 & ERR_MASK) == 0)
            return 0;
        if (soft_reset() != 0)
            return -1;
    }
    fprintf(stderr, "IOC_STUCK s2mm 0x%08x mm2s 0x%08x\n", rd(S2MM_SR), rd(MM2S_SR));
    return -1;
}

static int wait_ioc(uint32_t *s2_out, uint64_t *t_ioc)
{
    uint64_t deadline = now_ns() + 50000000ull;
    while (now_ns() < deadline) {
        uint32_t s2 = rd(S2MM_SR);
        uint32_t m2 = rd(MM2S_SR);
        if ((s2 & ERR_MASK) || (m2 & ERR_MASK)) {
            fprintf(stderr, "DMA_ERR s2mm 0x%08x mm2s 0x%08x\n", s2, m2);
            return -1;
        }
        if ((s2 & IOC) && (m2 & IOC)) {
            *t_ioc = now_ns();
            *s2_out = s2;
            return 0;
        }
    }
    fprintf(stderr, "TIMEOUT s2mm 0x%08x mm2s 0x%08x\n", rd(S2MM_SR), rd(MM2S_SR));
    return -1;
}

static int tail_all_aa(void)
{
    int i;
    for (i = 88; i < 96; i++) {
        if (dst_map[i] != 0xAA)
            return 0;
    }
    return 1;
}

static void copy_out(uint8_t *dst)
{
    int i;
    for (i = 0; i < OUT_BYTES; i++)
        dst[i] = dst_map[i];
}

static int32_t lsb_at(const uint8_t *raw, int k)
{
    return (int32_t)(int16_t)((uint16_t)raw[k * 4] | ((uint16_t)raw[k * 4 + 1] << 8));
}

static int max_lsb(const uint8_t *raw, const int32_t *golden)
{
    int k, err = 0;
    for (k = 0; k < OUT_DIM; k++) {
        int diff = lsb_at(raw, k) - golden[k];
        if (diff < 0)
            diff = -diff;
        if (diff > err)
            err = diff;
    }
    return err;
}

static void hex_out(FILE *fp, const uint8_t *raw)
{
    int i;
    for (i = 0; i < OUT_BYTES; i++)
        fprintf(fp, "%02x", raw[i]);
}

static const uint32_t EDGES[] = {
    100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000
};
#define NBINS 14

static int bin_of(uint32_t ns)
{
    int i;
    for (i = 0; i < NBINS - 1; i++) {
        if (ns < EDGES[i])
            return i;
    }
    return NBINS - 1;
}

static int cmp_u32(const void *a, const void *b)
{
    uint32_t da = *(const uint32_t *)a;
    uint32_t db = *(const uint32_t *)b;
    return (da > db) - (da < db);
}

static uint32_t pct_of(uint32_t *v, int n, int pct)
{
    size_t k;
    if (n < 1)
        return 0;
    qsort(v, (size_t)n, sizeof(uint32_t), cmp_u32);
    k = (size_t)((n - 1) * (double)pct / 100.0);
    return v[k];
}

static void *load_file(const char *path, size_t need)
{
    FILE *fp = fopen(path, "rb");
    void *buf;
    size_t n;
    if (!fp) {
        perror(path);
        return NULL;
    }
    buf = malloc(need);
    n = buf ? fread(buf, 1, need, fp) : 0;
    fclose(fp);
    if (n != need) {
        fprintf(stderr, "short read %s\n", path);
        free(buf);
        return NULL;
    }
    return buf;
}

int main(int argc, char **argv)
{
    int nframes, seen = 0, i;
    int first_clean = 0, tail_timeout = 0, differ = 0, bad1 = 0, bad2 = 0, bad3 = 0;
    int dumped = 0;
    uint32_t hist[NBINS];
    uint32_t delay_max = 0;
    uint32_t *delays = NULL;
    const uint8_t *payloads;
    const int32_t *golden;
    uint8_t prev[3][OUT_BYTES];
    FILE *ev;
    uint64_t t_begin;

    if (argc != 4) {
        fprintf(stderr, "usage: %s <nframes> payloads golden\n", argv[0]);
        return 2;
    }
    nframes = atoi(argv[1]);
    if (nframes < 1)
        return 2;
    if (!pl_operating()) {
        fprintf(stderr, "PL not operating\n");
        return 2;
    }
    if (map_all() != 0)
        return 3;
    payloads = load_file(argv[2], (size_t)SPAN * IN_BYTES);
    golden = load_file(argv[3], (size_t)SPAN * OUT_DIM * sizeof(int32_t));
    if (!payloads || !golden)
        return 2;
    if (nframes <= 200000)
        delays = calloc((size_t)nframes, sizeof(uint32_t));
    memset(hist, 0, sizeof hist);
    ev = fopen("/tmp/edgeai_bench/v8_x3_events.jsonl", "w");
    if (soft_reset() != 0)
        return 3;
    t_begin = now_ns();
    for (i = 0; i < nframes; i++) {
        int idx = i % SPAN;
        int k, spins = 0, timed_out = 0, err1, err2, err3 = 0, diff;
        uint32_t s2 = 0, delay = 0;
        uint64_t t_ioc = 0, t_vis, t_a;
        uint8_t raw1[OUT_BYTES], raw2[OUT_BYTES], raw3[OUT_BYTES];
        for (k = 0; k < OUT_BYTES; k++)
            dst_map[k] = 0xAA;
        msync((void *)dst_map, OUT_BYTES, MS_SYNC);
        memcpy(src_map, payloads + (size_t)idx * IN_BYTES, IN_BYTES);
        msync(src_map, IN_BYTES, MS_SYNC);
        if (ensure_idle() != 0)
            return 3;
        wr(S2MM_DA, DST_PHYS);
        wr(S2MM_DA_MSB, 0);
        wr(S2MM_CR, rd(S2MM_CR) | 1u);
        wr(S2MM_LEN, OUT_BYTES);
        wr(MM2S_SA, SRC_PHYS);
        wr(MM2S_SA_MSB, 0);
        wr(MM2S_CR, rd(MM2S_CR) | 1u);
        wr(MM2S_LEN, IN_BYTES);
        if (wait_ioc(&s2, &t_ioc) != 0)
            return 3;
        if (!tail_all_aa()) {
            t_vis = now_ns();
            first_clean++;
        } else {
            for (;;) {
                spins++;
                if (!tail_all_aa()) {
                    t_vis = now_ns();
                    break;
                }
                if (now_ns() - t_ioc > 1000000ull) {
                    t_vis = now_ns();
                    timed_out = 1;
                    tail_timeout++;
                    break;
                }
            }
        }
        delay = (uint32_t)(t_vis - t_ioc);
        if (delay > delay_max)
            delay_max = delay;
        hist[bin_of(delay)]++;
        if (delays)
            delays[seen] = delay;
        copy_out(raw1);
        t_a = now_ns();
        while (now_ns() - t_a < 10000ull)
            ;
        copy_out(raw2);
        diff = memcmp(raw1, raw2, OUT_BYTES) != 0;
        if (diff)
            differ++;
        err1 = max_lsb(raw1, golden + idx * OUT_DIM);
        err2 = max_lsb(raw2, golden + idx * OUT_DIM);
        if (err1)
            bad1++;
        if (err2)
            bad2++;
        if (rd(S2MM_LEN) != OUT_BYTES || (s2 & ERR_MASK) || timed_out || diff || err2) {
            uint64_t t_ms = now_ns();
            while (now_ns() - t_ms < 1000000ull)
                ;
            copy_out(raw3);
            err3 = max_lsb(raw3, golden + idx * OUT_DIM);
            if (err3)
                bad3++;
            if (ev && dumped < 20) {
                fprintf(ev,
                        "{\"frame\":%d,\"idx\":%d,\"delay_ns\":%u,\"spins\":%d,\"timeout\":%d,"
                        "\"diff10us\":%d,\"lsb1\":%d,\"lsb2\":%d,\"lsb_1ms\":%d,"
                        "\"s2mm\":\"0x%08x\",\"s2mm_len\":%u,\"mm2s\":\"0x%08x\",",
                        i, idx, delay, spins, timed_out, diff, err1, err2, err3,
                        s2, rd(S2MM_LEN), rd(MM2S_SR));
                fputs("\"raw1\":\"", ev);
                hex_out(ev, raw1);
                fputs("\",\"raw2\":\"", ev);
                hex_out(ev, raw2);
                fputs("\",\"raw_1ms\":\"", ev);
                hex_out(ev, raw3);
                fputs("\",\"prev\":[", ev);
                for (k = 0; k < 3; k++) {
                    fputs(k ? ",\"" : "\"", ev);
                    hex_out(ev, prev[k]);
                    fputc('"', ev);
                }
                fputs("]}\n", ev);
                fflush(ev);
                dumped++;
            }
            fprintf(stderr, "EVENT frame %d delay_ns %u lsb1 %d lsb2 %d lsb1ms %d diff %d timeout %d\n",
                    i, delay, err1, err2, err3, diff, timed_out);
        }
        memcpy(prev[i % 3], raw2, OUT_BYTES);
        seen++;
        if (seen % 20000 == 0)
            fprintf(stderr, "progress %d timeout %d diff %d bad1 %d bad2 %d\n",
                    seen, tail_timeout, differ, bad1, bad2);
        if (bad2 > 100 && bad2 * 20 > seen)
            break;
    }
    if (ev)
        fclose(ev);
    printf("POINT {\"seen\":%d,\"first_clean\":%d,\"tail_timeout\":%d,\"diff_10us\":%d,"
           "\"bad_immediate\":%d,\"bad_10us\":%d,\"bad_1ms\":%d,\"delay_max_ns\":%u,\"elapsed_s\":%.3f",
           seen, first_clean, tail_timeout, differ, bad1, bad2, bad3, delay_max,
           (now_ns() - t_begin) / 1.0e9);
    printf("}\n");
    if (delays && seen > 0) {
        printf("POINT2 {\"p50_ns\":%u,\"p99_ns\":%u,\"p999_ns\":%u}\n",
               pct_of(delays, seen, 50), pct_of(delays, seen, 99), pct_of(delays, seen, 999));
    }
    printf("HIST");
    for (i = 0; i < NBINS; i++)
        printf(" %u", hist[i]);
    printf("\n");
    return (tail_timeout || bad2) ? 5 : 0;
}
