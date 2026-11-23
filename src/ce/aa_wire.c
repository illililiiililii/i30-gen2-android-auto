#include "aa_wire.h"

#define FIRST 1U
#define LAST 2U
#define MAX_FRAME 0x4200U
#define MAX_MESSAGE (2U * 1024U * 1024U)

static unsigned read16(const uint8_t *bytes)
{
    return ((unsigned)bytes[0] << 8) | bytes[1];
}

enum I30WireResult i30_wire_header(const uint8_t *data, unsigned size, I30FrameHeader *header)
{
    if (size < 4U)
        return I30_WIRE_MORE;
    header->channel = data[0];
    header->flags = data[1];
    header->payload_bytes = (uint16_t)read16(data + 2);
    if ((header->flags & 0xf0U) || !header->payload_bytes || header->payload_bytes > MAX_FRAME)
        return I30_WIRE_INVALID;
    header->header_bytes = (header->flags & (FIRST | LAST)) == FIRST ? 8U : 4U;
    header->total_bytes = 0;
    if (size < header->header_bytes + header->payload_bytes)
        return I30_WIRE_MORE;
    if (header->header_bytes == 8U) {
        header->total_bytes = ((uint32_t)read16(data + 4) << 16) | read16(data + 6);
        if (header->total_bytes < 2U || header->total_bytes > MAX_MESSAGE)
            return I30_WIRE_INVALID;
    }
    return I30_WIRE_OK;
}

enum I30WireResult i30_aa_negotiate_version(const I30Link *link, uint16_t *peer_minor)
{
    /* Same version exchange as src/i30_receiver/protocol.py. */
    static const uint8_t request[] = {0, FIRST | LAST, 0, 6, 0, 1, 0, 1, 0, 6};
    uint8_t response[12];
    I30FrameHeader header;
    unsigned used = 0;
    enum I30WireResult result;

    if (link->write(link->context, request, sizeof(request)) != (int)sizeof(request))
        return I30_WIRE_IO;
    while (used < sizeof(response)) {
        unsigned need = (used < 4U ? 4U : sizeof(response)) - used;
        int count = link->read(link->context, response + used, need);
        if (count <= 0 || (unsigned)count > need)
            return I30_WIRE_IO;
        used += (unsigned)count;
        if (used == 4U && (response[0] != 0 || response[1] != (FIRST | LAST) || read16(response + 2) != 8U))
            return I30_WIRE_INVALID;
    }
    result = i30_wire_header(response, used, &header);
    if (result != I30_WIRE_OK || read16(response + 4) != 2U || read16(response + 6) != 1U || read16(response + 10))
        return I30_WIRE_INVALID;
    *peer_minor = (uint16_t)read16(response + 8);
    return I30_WIRE_OK;
}
