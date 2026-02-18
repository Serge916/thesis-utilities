// gcc -O2 -Wall -Wextra -o event-count event-count.c

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <errno.h>
#include <string.h>

#define EVENTS_PER_FRAME 15000

static unsigned popcount32(uint32_t x)
{
#if defined(__GNUC__) || defined(__clang__)
    return (unsigned)__builtin_popcount(x);
#else
    /* Portable fallback (Kernighan’s method) */
    unsigned c = 0;
    while (x)
    {
        x &= (x - 1);
        c++;
    }
    return c;
#endif
}

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        fprintf(stderr, "Usage: %s <path-to-txt>\n", argv[0]);
        return 2;
    }

    const char *path = argv[1];
    FILE *f = fopen(path, "r");
    if (!f)
    {
        fprintf(stderr, "Error: fopen('%s'): %s\n", path, strerror(errno));
        return 1;
    }

    char *line = NULL;
    size_t cap = 0;
    uint64_t total = 0;
    unsigned long long lineno = 0;

    while (getline(&line, &cap, f) != -1)
    {
        lineno++;

        /* Skip leading whitespace */
        char *p = line;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
            p++;

        /* Skip empty lines */
        if (*p == '\0')
            continue;

        errno = 0;
        char *end = NULL;

        /* Parse as 64-bit hex (handles optional 0x too) */
        uint64_t v = strtoull(p, &end, 16);

        if (p == end)
        {
            fprintf(stderr, "Line %llu: not a hex number: %s", lineno, line);
            free(line);
            fclose(f);
            return 1;
        }
        if (errno == ERANGE)
        {
            fprintf(stderr, "Line %llu: hex number out of range: %s", lineno, line);
            free(line);
            fclose(f);
            return 1;
        }

        /* Ensure rest of line is only whitespace/newline */
        while (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n')
            end++;
        if (*end != '\0')
        {
            fprintf(stderr, "Line %llu: trailing junk after hex: %s", lineno, line);
            free(line);
            fclose(f);
            return 1;
        }

        /* Payload = lower 32 bits */
        uint32_t payload = (uint32_t)(v & 0xFFFFFFFFu);

        /* Add number of set bits in payload */
        total += popcount32(payload);
    }

    free(line);
    fclose(f);

    size_t frames = total / EVENTS_PER_FRAME;
    printf("Quantity of events is %" PRIu64 ", equivalent to %" PRIu64 " SpikeVision frames.\n", total, frames);
    return 0;
}
