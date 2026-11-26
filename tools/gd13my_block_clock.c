#include <stdint.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

typedef void (*BlockHook)(void *, uint64_t, uint32_t, void *);

typedef struct {
    uint64_t units;
    uint64_t service_at;
    uint64_t prefetch_pc;
    uint64_t watch_vfp;
    BlockHook service;
} BlockClock;

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
