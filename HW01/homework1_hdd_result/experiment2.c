#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifdef _WIN32
#include <windows.h>
#define BINARY_FLAG O_BINARY
typedef LARGE_INTEGER timer_point;
static int timer_now(timer_point *point) {
    return QueryPerformanceCounter(point) ? 0 : -1;
}
static double elapsed_ms(timer_point start, timer_point end) {
    LARGE_INTEGER frequency;
    QueryPerformanceFrequency(&frequency);
    return (double)(end.QuadPart - start.QuadPart) * 1000.0 /
           (double)frequency.QuadPart;
}
#else
#define BINARY_FLAG 0
typedef struct timespec timer_point;
static int timer_now(timer_point *point) {
    return clock_gettime(CLOCK_MONOTONIC, point);
}
static double elapsed_ms(timer_point start, timer_point end) {
    return (double)(end.tv_sec - start.tv_sec) * 1000.0 +
           (double)(end.tv_nsec - start.tv_nsec) / 1000000.0;
}
#endif

#define CHUNK_SIZE (256u * 1024u)
#define READ_COUNT 1024u
#define FILE_SIZE ((uint64_t)CHUNK_SIZE * READ_COUNT)
#define DATA_FILE "19"

static int write_all(int fd, const unsigned char *buf, size_t len) {
    size_t done = 0;
    while (done < len) {
        ssize_t n = write(fd, buf + done, len - done);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (n == 0) {
            errno = EIO;
            return -1;
        }
        done += (size_t)n;
    }
    return 0;
}

static int read_all(int fd, unsigned char *buf, size_t len) {
    size_t done = 0;
    while (done < len) {
        ssize_t n = read(fd, buf + done, len - done);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (n == 0) {
            errno = EIO; /* Unexpected end of file. */
            return -1;
        }
        done += (size_t)n;
    }
    return 0;
}

static uint32_t next_random(uint32_t *state) {
    /* xorshift32: small reproducible generator, sufficient for offsets. */
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static void report_error(const char *operation) {
    perror(operation);
}

int main(void) {
    unsigned char *buffer = (unsigned char *)malloc(CHUNK_SIZE);
    if (buffer == NULL) {
        report_error("malloc");
        return EXIT_FAILURE;
    }

    for (size_t i = 0; i < CHUNK_SIZE; ++i)
        buffer[i] = (unsigned char)((i % 255u) + 1u);

    /* Build file 19 as 1024 consecutive 256 KB blocks (256 MB total). */
    int fd = open(DATA_FILE, O_WRONLY | O_CREAT | O_TRUNC | BINARY_FLAG, 0644);
    if (fd < 0) {
        report_error("open file 19 for writing");
        free(buffer);
        return EXIT_FAILURE;
    }
    for (uint32_t i = 0; i < READ_COUNT; ++i) {
        if (write_all(fd, buffer, CHUNK_SIZE) != 0) {
            report_error("write file 19");
            close(fd);
            free(buffer);
            return EXIT_FAILURE;
        }
    }
    if (close(fd) != 0) {
        report_error("close file 19 after writing");
        free(buffer);
        return EXIT_FAILURE;
    }

    printf("Created file %s: %llu bytes (256 MiB)\n", DATA_FILE,
           (unsigned long long)FILE_SIZE);

    FILE *csv = fopen("experiment2_results.csv", "w");
    if (csv == NULL) {
        report_error("experiment2_results.csv");
        free(buffer);
        return EXIT_FAILURE;
    }
    fprintf(csv, "test,read_count,bytes_per_read,total_bytes,elapsed_ms\n");

    /* Sequential test: one pass over the complete file. */
    fd = open(DATA_FILE, O_RDONLY | BINARY_FLAG);
    if (fd < 0) {
        report_error("open file 19 for sequential read");
        fclose(csv);
        free(buffer);
        return EXIT_FAILURE;
    }
    timer_point start, end;
    if (timer_now(&start) != 0) {
        fprintf(stderr, "Failed to read performance timer\n");
        close(fd); fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    uint64_t bytes_read = 0;
    while (bytes_read < FILE_SIZE) {
        size_t amount = CHUNK_SIZE;
        if (FILE_SIZE - bytes_read < amount)
            amount = (size_t)(FILE_SIZE - bytes_read);
        if (read_all(fd, buffer, amount) != 0) {
            report_error("sequential read");
            close(fd); fclose(csv); free(buffer);
            return EXIT_FAILURE;
        }
        bytes_read += amount;
    }
    if (timer_now(&end) != 0) {
        fprintf(stderr, "Failed to read performance timer\n");
        close(fd); fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    if (close(fd) != 0) {
        report_error("close after sequential read");
        fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    double sequential_ms = elapsed_ms(start, end);
    fprintf(csv, "sequential,%u,%u,%llu,%.6f\n", READ_COUNT, CHUNK_SIZE,
            (unsigned long long)FILE_SIZE, sequential_ms);
    printf("Sequential read: %.3f ms (%llu bytes)\n", sequential_ms,
           (unsigned long long)FILE_SIZE);

    /* Random test: 1024 reads of 256 KB at valid offsets in file 19. */
    fd = open(DATA_FILE, O_RDONLY | BINARY_FLAG);
    if (fd < 0) {
        report_error("open file 19 for random read");
        fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    uint64_t max_offset = FILE_SIZE - CHUNK_SIZE;
    uint32_t rng = 0xA341316Cu;
    if (timer_now(&start) != 0) {
        fprintf(stderr, "Failed to read performance timer\n");
        close(fd); fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    for (uint32_t i = 0; i < READ_COUNT; ++i) {
        uint64_t offset = (uint64_t)next_random(&rng) % (max_offset + 1u);
        if (lseek(fd, (off_t)offset, SEEK_SET) == (off_t)-1) {
            report_error("lseek");
            close(fd); fclose(csv); free(buffer);
            return EXIT_FAILURE;
        }
        if (read_all(fd, buffer, CHUNK_SIZE) != 0) {
            report_error("random read");
            close(fd); fclose(csv); free(buffer);
            return EXIT_FAILURE;
        }
    }
    if (timer_now(&end) != 0) {
        fprintf(stderr, "Failed to read performance timer\n");
        close(fd); fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    if (close(fd) != 0) {
        report_error("close after random read");
        fclose(csv); free(buffer);
        return EXIT_FAILURE;
    }
    double random_ms = elapsed_ms(start, end);
    fprintf(csv, "random,%u,%u,%llu,%.6f\n", READ_COUNT, CHUNK_SIZE,
            (unsigned long long)FILE_SIZE, random_ms);
    printf("Random read:     %.3f ms (%u reads x %u bytes)\n", random_ms,
           READ_COUNT, CHUNK_SIZE);

    if (fclose(csv) != 0) {
        report_error("close results CSV");
        free(buffer);
        return EXIT_FAILURE;
    }
    free(buffer);
    printf("Results saved to experiment2_results.csv\n");
    return EXIT_SUCCESS;
}
