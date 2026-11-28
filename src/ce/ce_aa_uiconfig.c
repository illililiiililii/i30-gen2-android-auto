#include "ce_aa_uiconfig.h"

#include <string.h>

#define UPDATE_UI_CONFIG_REQUEST 0x8009U
#define UPDATE_UI_CONFIG_REPLY 0x800AU
#define INSET_FIELD_COUNT 4U

static uint8_t *put_varint(uint8_t *out, uint64_t value)
{
    while (value >= 128U) {
        *out++ = (uint8_t)(value | 128U);
        value >>= 7;
    }
    *out++ = (uint8_t)value;
    return out;
}

static unsigned varint_bytes(uint64_t value)
{
    unsigned size = 1;
    while (value >= 128U) {
        value >>= 7;
        ++size;
    }
    return size;
}

static unsigned inset_bytes(const I30UiInsets *insets)
{
    const uint32_t values[INSET_FIELD_COUNT] = {insets->top, insets->bottom,
                                                insets->left, insets->right};
    unsigned size = 0;
    for (unsigned i = 0; i < INSET_FIELD_COUNT; ++i)
        size += 1U + varint_bytes(values[i]); /* Tag plus uint32 varint. */
    return size;
}

void i30_uiconfig_experiment_default(I30UiConfig *config)
{
    if (!config)
        return;
    config->present = I30_UI_CONFIG_PRESENT;
    config->margins.top = I30_UI_CONFIG_MARGINS_TOP;
    config->margins.bottom = I30_UI_CONFIG_MARGINS_BOTTOM;
    config->margins.left = I30_UI_CONFIG_MARGINS_LEFT;
    config->margins.right = I30_UI_CONFIG_MARGINS_RIGHT;
    config->content.top = I30_UI_CONFIG_CONTENT_TOP;
    config->content.bottom = I30_UI_CONFIG_CONTENT_BOTTOM;
    config->content.left = I30_UI_CONFIG_CONTENT_LEFT;
    config->content.right = I30_UI_CONFIG_CONTENT_RIGHT;
    config->stable.top = I30_UI_CONFIG_STABLE_TOP;
    config->stable.bottom = I30_UI_CONFIG_STABLE_BOTTOM;
    config->stable.left = I30_UI_CONFIG_STABLE_LEFT;
    config->stable.right = I30_UI_CONFIG_STABLE_RIGHT;
}

static uint8_t *encode_insets(uint8_t *out, const I30UiInsets *insets)
{
    static const uint8_t tags[INSET_FIELD_COUNT] = {0x08, 0x10, 0x18, 0x20};
    const uint32_t values[INSET_FIELD_COUNT] = {insets->top, insets->bottom,
                                                insets->left, insets->right};
    for (unsigned i = 0; i < INSET_FIELD_COUNT; ++i) {
        *out++ = tags[i];
        out = put_varint(out, values[i]);
    }
    return out;
}

unsigned i30_uiconfig_encode_ui(uint8_t *out, unsigned capacity, const I30UiConfig *config)
{
    unsigned required = 0;
    uint8_t *end;
    if (!out || !config)
        return 0;
    if (config->present & I30_UI_CONFIG_MARGINS)
        required += 1U + varint_bytes(inset_bytes(&config->margins)) + inset_bytes(&config->margins);
    if (config->present & I30_UI_CONFIG_CONTENT)
        required += 1U + varint_bytes(inset_bytes(&config->content)) + inset_bytes(&config->content);
    if (config->present & I30_UI_CONFIG_STABLE)
        required += 1U + varint_bytes(inset_bytes(&config->stable)) + inset_bytes(&config->stable);
    if (!required || required > capacity)
        return 0;
    end = out;
    if (config->present & I30_UI_CONFIG_MARGINS) {
        unsigned size = inset_bytes(&config->margins);
        *end++ = 0x0a; /* UiConfig.margins */
        end = put_varint(end, size);
        end = encode_insets(end, &config->margins);
    }
    if (config->present & I30_UI_CONFIG_CONTENT) {
        unsigned size = inset_bytes(&config->content);
        *end++ = 0x12; /* UiConfig.content_insets */
        end = put_varint(end, size);
        end = encode_insets(end, &config->content);
    }
    if (config->present & I30_UI_CONFIG_STABLE) {
        unsigned size = inset_bytes(&config->stable);
        *end++ = 0x1a; /* UiConfig.stable_content_insets */
        end = put_varint(end, size);
        end = encode_insets(end, &config->stable);
    }
    return (unsigned)(end - out);
}

unsigned i30_uiconfig_encode(uint8_t *out, unsigned capacity, unsigned message_id,
                             const I30UiConfig *config)
{
    uint8_t body[3U * (2U + INSET_FIELD_COUNT * 5U)]; /* Three fields, each with a uint32 varint per edge. */
    unsigned body_size, used;
    uint8_t *end;
    if (!out || (message_id != UPDATE_UI_CONFIG_REQUEST && message_id != UPDATE_UI_CONFIG_REPLY))
        return 0;
    body_size = i30_uiconfig_encode_ui(body, sizeof(body), config);
    if (!body_size)
        return 0;
    used = 2U + 1U + varint_bytes(body_size) + body_size;
    if (capacity < used)
        return 0;
    out[0] = (uint8_t)(message_id >> 8);
    out[1] = (uint8_t)message_id;
    out[2] = 0x0a; /* UpdateUiConfigRequest/Reply.ui_config */
    end = put_varint(out + 3, body_size);
    memcpy(end, body, body_size);
    return used;
}

static int take_varint(const uint8_t **cursor, unsigned *left, uint64_t *value)
{
    uint64_t result = 0;
    for (unsigned shift = 0; shift < 64U && *left; shift += 7) {
        uint8_t byte = **cursor;
        ++*cursor;
        --*left;
        if (shift == 63U && byte > 1U)
            return 0;
        result |= (uint64_t)(byte & 127U) << shift;
        if (!(byte & 128U)) {
            *value = result;
            return 1;
        }
    }
    return 0;
}

static int take_uint32(const uint8_t **cursor, unsigned *left, uint32_t *value)
{
    uint64_t raw;
    if (!take_varint(cursor, left, &raw) || raw > 0xffffffffU)
        return 0;
    *value = (uint32_t)raw;
    return 1;
}

static int skip_field(uint64_t tag, const uint8_t **cursor, unsigned *left)
{
    uint64_t length;
    unsigned wire = (unsigned)(tag & 7U);
    if (!(tag >> 3))
        return 0;
    if (wire == 0)
        return take_varint(cursor, left, &length);
    if (wire == 1)
        return *left >= 8U ? (*cursor += 8, *left -= 8U, 1) : 0;
    if (wire == 2) {
        if (!take_varint(cursor, left, &length) || length > *left)
            return 0;
        *cursor += (unsigned)length;
        *left -= (unsigned)length;
        return 1;
    }
    if (wire == 5)
        return *left >= 4U ? (*cursor += 4, *left -= 4U, 1) : 0;
    return 0;
}

static int decode_insets(const uint8_t *body, unsigned length, I30UiInsets *insets)
{
    const uint8_t *cursor = body;
    unsigned left = length;
    memset(insets, 0, sizeof(*insets));
    while (left) {
        uint64_t tag;
        uint32_t value;
        if (!take_varint(&cursor, &left, &tag) || !(tag >> 3))
            return 0;
        if ((tag & 7U) == 0 && (tag >> 3) >= 1 && (tag >> 3) <= INSET_FIELD_COUNT) {
            if (!take_uint32(&cursor, &left, &value))
                return 0;
            if ((tag >> 3) == 1)
                insets->top = value;
            else if ((tag >> 3) == 2)
                insets->bottom = value;
            else if ((tag >> 3) == 3)
                insets->left = value;
            else
                insets->right = value;
        } else if (!skip_field(tag, &cursor, &left)) {
            return 0;
        }
    }
    return 1;
}

static int decode_config(const uint8_t *body, unsigned length, I30UiConfig *config)
{
    const uint8_t *cursor = body;
    unsigned left = length;
    while (left) {
        uint64_t tag, size;
        unsigned field;
        if (!take_varint(&cursor, &left, &tag) || !(tag >> 3))
            return 0;
        field = (unsigned)(tag >> 3);
        if ((tag & 7U) == 2 && field >= 1 && field <= 3) {
            if (!take_varint(&cursor, &left, &size) || size > left)
                return 0;
            if (field == 1) {
                if (!decode_insets(cursor, (unsigned)size, &config->margins))
                    return 0;
                config->present |= I30_UI_CONFIG_MARGINS;
            } else if (field == 2) {
                if (!decode_insets(cursor, (unsigned)size, &config->content))
                    return 0;
                config->present |= I30_UI_CONFIG_CONTENT;
            } else {
                if (!decode_insets(cursor, (unsigned)size, &config->stable))
                    return 0;
                config->present |= I30_UI_CONFIG_STABLE;
            }
            cursor += (unsigned)size;
            left -= (unsigned)size;
        } else if (!skip_field(tag, &cursor, &left)) {
            return 0;
        }
    }
    return 1;
}

int i30_uiconfig_decode(const uint8_t *body, unsigned length, I30UiConfig *config)
{
    const uint8_t *cursor = body;
    unsigned left = length;
    int seen = 0;
    if (!body || !config || !length)
        return 0;
    memset(config, 0, sizeof(*config));
    while (left) {
        uint64_t tag, size;
        if (!take_varint(&cursor, &left, &tag) || !(tag >> 3))
            return 0;
        if ((tag & 7U) == 2 && (tag >> 3) == 1) {
            if (!take_varint(&cursor, &left, &size) || size > left)
                return 0;
            if (!decode_config(cursor, (unsigned)size, config))
                return 0;
            cursor += (unsigned)size;
            left -= (unsigned)size;
            seen = 1;
        } else if (!skip_field(tag, &cursor, &left)) {
            return 0;
        }
    }
    return seen;
}
