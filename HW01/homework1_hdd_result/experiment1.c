#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef _WIN32
#include <windows.h>
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
typedef struct timespec timer_point;
static int timer_now(timer_point *point) {
    return clock_gettime(CLOCK_MONOTONIC, point);
}
static double elapsed_ms(timer_point start, timer_point end) {
    return (double)(end.tv_sec - start.tv_sec) * 1000.0 +
           (double)(end.tv_nsec - start.tv_nsec) / 1000000.0;
}
#endif

#define DATA_SIZE (256u * 1024u)
#define PHASES 256
#define FIRST_EXPONENT 0
#define LAST_EXPONENT 17

/* write() may write fewer bytes than requested; keep going until complete. */
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

int main(void) {
    unsigned char *buffer = (unsigned char *)malloc(DATA_SIZE);
    if (buffer == NULL) {
        perror("malloc");
        return EXIT_FAILURE;
    }

    for (size_t i = 0; i < DATA_SIZE; ++i)
        buffer[i] = (unsigned char)((i % 255u) + 1u);

    FILE *csv = fopen("experiment1_results.csv", "w");
    if (csv == NULL) {
        perror("experiment1_results.csv");
        free(buffer);
        return EXIT_FAILURE;
    }
    fprintf(csv, "phase,file,block_size_bytes,elapsed_ms\n");

    printf("Experiment 1: %u bytes per phase, %d phases per block size\n",
           DATA_SIZE, PHASES);
    printf("Results will be saved to experiment1_results.csv\n");

    for (int phase = 1; phase <= PHASES; ++phase) {
        for (int exponent = FIRST_EXPONENT; exponent <= LAST_EXPONENT; ++exponent) {
            size_t block_size = (size_t)1u << exponent;
            char filename[3];
            snprintf(filename, sizeof(filename), "%02d", exponent + 1);

            int fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC, 0644);
            if (fd < 0) {
                perror(filename);
                fclose(csv);
                free(buffer);
                return EXIT_FAILURE;
            }

            timer_point start, end;
            if (timer_now(&start) != 0) {
                fprintf(stderr, "Failed to read performance timer\n");
                close(fd);
                fclose(csv);
                free(buffer);
                return EXIT_FAILURE;
            }

            size_t offset = 0;
            while (offset < DATA_SIZE) {
                size_t amount = block_size;
                if (amount > DATA_SIZE - offset) amount = DATA_SIZE - offset;
                if (write_all(fd, buffer + offset, amount) != 0) {
                    perror("write");
                    close(fd);
                    fclose(csv);
                    free(buffer);
                    return EXIT_FAILURE;
                }
                offset += amount;
            }

            if (timer_now(&end) != 0) {
                fprintf(stderr, "Failed to read performance timer\n");
                close(fd);
                fclose(csv);
                free(buffer);
                return EXIT_FAILURE;
            }

            /* Close outside the timed interval, as the handout times write(). */
            if (close(fd) != 0) {
                perror("close");
                fclose(csv);
                free(buffer);
                return EXIT_FAILURE;
            }

            double ms = elapsed_ms(start, end);
            fprintf(csv, "%d,%s,%zu,%.6f\n", phase, filename, block_size, ms);
            if (phase == 1)
                printf("file %s, block %6zu bytes: first run %.3f ms\n",
                       filename, block_size, ms);
        }
        if (phase % 32 == 0) {
            fflush(csv);
            printf("Completed phase %d/%d\n", phase, PHASES);
        }
    }

    if (fclose(csv) != 0) {
        perror("fclose results");
        free(buffer);
        return EXIT_FAILURE;
    }
    free(buffer);
    printf("Done. 256 measurements per block size are in experiment1_results.csv.\n");
    return EXIT_SUCCESS;
}
