#define _POSIX_C_SOURCE 200809L
/* X2 production hot path. One initial reset, then each frame:
 * poison, copy src, clear IOC and read it back as 0, start, busy-wait,
 * require S2MM length 96 and no error, then read 96 bytes.
 * Does not touch PL0_REF_CTRL.
 */
#include <errno.h>
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
#define NCLASS 10
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

static volatile uint32_t *reg;
static uint8_t *src_map;
static uint8_t *dst_map;
static int mem_fd;

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1.0e6;
}

static uint32_t rd(unsigned off)
{
    return reg[off >> 2];
}

static void wr(unsigned off, uint32_t v)
{
    reg[off >> 2] = v;
}

static int map_all(void)
{
    mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (mem_fd < 0) {
        perror("open /dev/mem");
        return -1;
    }
    reg = mmap(NULL, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, DMA_PHYS);
    src_map = mmap(NULL, 8192, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, SRC_PHYS);
    dst_map = mmap(NULL, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, DST_PHYS);
    if (reg == MAP_FAILED || src_map == MAP_FAILED || dst_map == MAP_FAILED) {
        perror("mmap");
        return -1;
    }
    return 0;
}

static int pl_operating(void)
{
    char buf[64];
    FILE *fp = fopen("/sys/class/fpga_manager/fpga0/state", "r");
    if (!fp) {
        perror("fpga state");
        return 0;
    }
    if (!fgets(buf, sizeof buf, fp)) {
        fclose(fp);
        return 0;
    }
    fclose(fp);
    return strncmp(buf, "operating", 9) == 0;
}

static int soft_reset(void)
{
    double deadline = now_ms() + 100.0;
    wr(MM2S_CR, rd(MM2S_CR) | 4u);
    wr(S2MM_CR, rd(S2MM_CR) | 4u);
    while (now_ms() < deadline) {
        if ((rd(MM2S_CR) & 4u) == 0 && (rd(S2MM_CR) & 4u) == 0)
            return 0;
    }
    fprintf(stderr, "RESET_FAIL mm2s 0x%08x s2mm 0x%08x\n", rd(MM2S_CR), rd(S2MM_CR));
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

static int wait_ioc(uint32_t *s2_out)
{
    double deadline = now_ms() + 50.0;
    while (now_ms() < deadline) {
        uint32_t s2 = rd(S2MM_SR);
        uint32_t m2 = rd(MM2S_SR);
        if ((s2 & ERR_MASK) || (m2 & ERR_MASK)) {
            fprintf(stderr, "DMA_ERR s2mm 0x%08x mm2s 0x%08x\n", s2, m2);
            *s2_out = s2;
            return -1;
        }
        if ((s2 & IOC) && (m2 & IOC)) {
            *s2_out = s2;
            return 0;
        }
    }
    fprintf(stderr, "TIMEOUT s2mm 0x%08x mm2s 0x%08x\n", rd(S2MM_SR), rd(MM2S_SR));
    return -1;
}

static int hole_aa(const uint8_t *raw)
{
    int k;
    for (k = 0; k < OUT_DIM; k++) {
        if (raw[k * 4 + 2] == 0xAA && raw[k * 4 + 3] == 0xAA)
            return k;
    }
    return -1;
}

static int32_t lsb_at(const uint8_t *raw, int k)
{
    return (int32_t)(int16_t)((uint16_t)raw[k * 4] | ((uint16_t)raw[k * 4 + 1] << 8));
}

static int argmax_dense(const int32_t *lsb, const float *w, const float *bias)
{
    int best = 0;
    int i, j;
    float best_v = -1.0e30f;
    for (j = 0; j < NCLASS; j++) {
        float s = bias[j];
        for (i = 0; i < OUT_DIM; i++)
            s += ((float)lsb[i] / 1024.0f) * w[i * NCLASS + j];
        if (s > best_v) {
            best_v = s;
            best = j;
        }
    }
    return best;
}

static int cmp_double(const void *a, const void *b)
{
    double da = *(const double *)a;
    double db = *(const double *)b;
    return (da > db) - (da < db);
}

static double median(double *v, int n)
{
    qsort(v, (size_t)n, sizeof(double), cmp_double);
    if (n % 2)
        return v[n / 2];
    return 0.5 * (v[n / 2 - 1] + v[n / 2]);
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
    if (!buf) {
        fclose(fp);
        return NULL;
    }
    n = fread(buf, 1, need, fp);
    fclose(fp);
    if (n != need) {
        fprintf(stderr, "short read %s %zu/%zu\n", path, n, need);
        free(buf);
        return NULL;
    }
    return buf;
}

int main(int argc, char **argv)
{
    int soak = 0;
    int n = 0;
    double soak_s = 0.0;
    const uint8_t *payloads;
    const int32_t *golden;
    const int32_t *top1;
    const float *weight;
    const float *bias;
    double *t_poison, *t_src, *t_idle, *t_start, *t_wait, *t_read, *t_decode, *t_dense, *t_loop;
    int stored = 0;
    int cap = 0;
    int seen = 0;
    int events = 0;
    int max_lsb = 0;
    double t_begin, t_end;
    int i;

    if (argc != 8) {
        fprintf(stderr, "usage: %s bench|soak <n|seconds> payloads golden top1 weight bias\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "soak") == 0)
        soak = 1;
    else if (strcmp(argv[1], "bench") != 0)
        return 2;
    if (!pl_operating()) {
        fprintf(stderr, "PL not operating\n");
        return 2;
    }
    if (map_all() != 0)
        return 3;
    int span;
    if (soak) {
        soak_s = atof(argv[2]);
        span = 10000;
        n = 20000000;
        cap = 2000;
    } else {
        n = atoi(argv[2]);
        span = n;
        cap = n;
    }
    payloads = load_file(argv[3], (size_t)span * IN_BYTES);
    golden = load_file(argv[4], (size_t)span * OUT_DIM * sizeof(int32_t));
    top1 = load_file(argv[5], (size_t)span * sizeof(int32_t));
    weight = load_file(argv[6], OUT_DIM * NCLASS * sizeof(float));
    bias = load_file(argv[7], NCLASS * sizeof(float));
    if (!payloads || !golden || !top1 || !weight || !bias)
        return 2;
    t_poison = calloc((size_t)cap, sizeof(double));
    t_src = calloc((size_t)cap, sizeof(double));
    t_idle = calloc((size_t)cap, sizeof(double));
    t_start = calloc((size_t)cap, sizeof(double));
    t_wait = calloc((size_t)cap, sizeof(double));
    t_read = calloc((size_t)cap, sizeof(double));
    t_decode = calloc((size_t)cap, sizeof(double));
    t_dense = calloc((size_t)cap, sizeof(double));
    t_loop = calloc((size_t)cap, sizeof(double));
    if (soft_reset() != 0)
        return 3;
    t_begin = now_ms();
    for (i = 0; i < n; i++) {
        uint8_t raw[OUT_BYTES];
        int32_t lsb[OUT_DIM];
        uint32_t s2 = 0;
        int k, err, aa, pred;
        double a, b, c, d, e, f, g, h, loop0;
        if (soak && (now_ms() - t_begin) >= soak_s * 1000.0)
            break;
        loop0 = now_ms();
        memset(dst_map, 0xAA, OUT_BYTES);
        msync(dst_map, OUT_BYTES, MS_SYNC);
        a = now_ms();
        int idx = i % span;
        memcpy(src_map, payloads + (size_t)idx * IN_BYTES, IN_BYTES);
        msync(src_map, IN_BYTES, MS_SYNC);
        b = now_ms();
        if (ensure_idle() != 0)
            return 3;
        c = now_ms();
        wr(S2MM_DA, DST_PHYS);
        wr(S2MM_DA_MSB, 0);
        wr(S2MM_CR, rd(S2MM_CR) | 1u);
        wr(S2MM_LEN, OUT_BYTES);
        wr(MM2S_SA, SRC_PHYS);
        wr(MM2S_SA_MSB, 0);
        wr(MM2S_CR, rd(MM2S_CR) | 1u);
        wr(MM2S_LEN, IN_BYTES);
        d = now_ms();
        if (wait_ioc(&s2) != 0)
            return 3;
        e = now_ms();
        if (rd(S2MM_LEN) != OUT_BYTES || (s2 & ERR_MASK)) {
            fprintf(stderr, "LEN_OR_ERR frame %d len %u s2mm 0x%08x\n", i, rd(S2MM_LEN), s2);
            return 5;
        }
        msync(dst_map, OUT_BYTES, MS_INVALIDATE | MS_SYNC);
        memcpy(raw, dst_map, OUT_BYTES);
        f = now_ms();
        err = 0;
        for (k = 0; k < OUT_DIM; k++) {
            int diff;
            lsb[k] = lsb_at(raw, k);
            diff = lsb[k] - golden[idx * OUT_DIM + k];
            if (diff < 0)
                diff = -diff;
            if (diff > err)
                err = diff;
        }
        g = now_ms();
        pred = argmax_dense(lsb, weight, bias);
        h = now_ms();
        aa = hole_aa(raw);
        if (aa >= 0 || err || pred != top1[idx]) {
            events++;
            fprintf(stderr, "MISMATCH frame %d lsb %d aa %d pred %d gold %d\n",
                    i, err, aa, pred, top1[idx]);
            return 5;
        }
        if (err > max_lsb)
            max_lsb = err;
        if (stored < cap) {
            t_poison[stored] = a - loop0;
            t_src[stored] = b - a;
            t_idle[stored] = c - b;
            t_start[stored] = d - c;
            t_wait[stored] = e - d;
            t_read[stored] = f - e;
            t_decode[stored] = g - f;
            t_dense[stored] = h - g;
            t_loop[stored] = h - loop0;
            stored++;
        }
        seen++;
        if (seen % 20000 == 0)
            fprintf(stderr, "progress %d\n", seen);
    }
    t_end = now_ms();
    if (stored < 1) {
        fprintf(stderr, "no frames\n");
        return 3;
    }
    {
        double poison = median(t_poison, stored);
        double src = median(t_src, stored);
        double idle = median(t_idle, stored);
        double start = median(t_start, stored);
        double wait = median(t_wait, stored);
        double read = median(t_read, stored);
        double decode = median(t_decode, stored);
        double dense = median(t_dense, stored);
        double loop = median(t_loop, stored);
        double ps = src + start + read + decode + dense;
        double sum = poison + src + idle + start + wait + read + decode + dense;
        printf("POINT {\"seen\":%d,\"events\":%d,\"max_lsb\":%d,\"elapsed_s\":%.3f,"
               "\"poison_ms\":%.4f,\"src_ms\":%.4f,\"idle_ms\":%.4f,\"start_ms\":%.4f,"
               "\"wait_ms\":%.4f,\"read_ms\":%.4f,\"decode_ms\":%.4f,\"dense_ms\":%.4f,"
               "\"loop_ms\":%.4f,\"sum_ms\":%.4f,\"ps_ms\":%.4f,\"gap_ms\":%.4f}\n",
               seen, events, max_lsb, (t_end - t_begin) / 1000.0,
               poison, src, idle, start, wait, read, decode, dense, loop, sum, ps, loop - sum);
    }
    return 0;
}
