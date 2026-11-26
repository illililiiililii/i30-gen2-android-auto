#include <stdint.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

typedef void (*BlockHook)(void *, uint64_t, uint32_t, void *);
typedef uint64_t (*MmioRead)(void *, uint64_t, unsigned, void *);

typedef struct {
    uint64_t units;
    uint64_t service_at;
    uint64_t prefetch_pc;
    uint64_t watch_vfp;
    BlockHook service;
} BlockClock;

typedef struct {
    const uint8_t *payload;
    uint64_t length;
    uint64_t position;
    uint64_t words_read;
    MmioRead read;
} MmcFifo;

EXPORT unsigned gd13my_clock_abi(void)
{
    return 1;
}

EXPORT void gd13my_clock_block(void *cpu, uint64_t address, uint32_t size, void *opaque)
{
    BlockClock *clock = opaque;
    clock->units += size / 4;
    if (clock->units >= clock->service_at || address == clock->prefetch_pc || clock->watch_vfp)
        clock->service(cpu, address, size, opaque);
}

EXPORT uint64_t gd13my_mmc_read(void *cpu, uint64_t offset, unsigned size, void *opaque)
{
    MmcFifo *fifo = opaque;
    uint64_t position = fifo->position;
    /* Python keeps ownership of sector-boundary status changes and DMA. */
    if (offset == 0x120 && size == 4 && position < fifo->length &&
        fifo->length - position > 4 && (position & 511) < 508) {
        const uint8_t *p = fifo->payload + position;
        fifo->position = position + 4;
        ++fifo->words_read;
        return p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    }
    return fifo->read(cpu, offset, size, 0);
}
