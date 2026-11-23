#ifndef I30_CE_AA_WIRE_H
#define I30_CE_AA_WIRE_H

#include <stdint.h>

enum I30WireResult {
    I30_WIRE_INVALID = -1,
    I30_WIRE_IO = -2,
    I30_WIRE_MORE = 0,
    I30_WIRE_OK = 1
};

typedef struct I30FrameHeader {
    uint8_t channel;
    uint8_t flags;
    uint16_t payload_bytes;
    uint32_t total_bytes;
    unsigned header_bytes;
} I30FrameHeader;

/* A read returns at most capacity bytes and retains any surplus for the next read.
 * A write returns bytes accepted. The adapter applies its own I/O deadlines. */
typedef struct I30Link {
    void *context;
    int (*read)(void *context, uint8_t *buffer, unsigned capacity);
    int (*write)(void *context, const uint8_t *buffer, unsigned size);
} I30Link;

enum I30WireResult i30_wire_header(const uint8_t *data, unsigned size, I30FrameHeader *header);
enum I30WireResult i30_aa_negotiate_version(const I30Link *link, uint16_t *peer_minor);

#endif
