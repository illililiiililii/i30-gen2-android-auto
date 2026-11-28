#ifndef I30_CE_AA_UICONFIG_H
#define I30_CE_AA_UICONFIG_H

#include "ce_minimal.h"

/* Experimental AARE UI configuration wire contract. The compiled defaults in
 * this tree keep the whole feature disabled; these values are only used when
 * an image is deliberately built with I30_UI_CONFIG_EXPERIMENT. */
enum {
    I30_UI_CONFIG_MARGINS = 1U,
    I30_UI_CONFIG_CONTENT = 2U,
    I30_UI_CONFIG_STABLE = 4U
};

typedef struct I30UiInsets {
    uint32_t top, bottom, left, right;
} I30UiInsets;

typedef struct I30UiConfig {
    unsigned present;
    I30UiInsets margins, content, stable;
} I30UiConfig;

/* Encode a bare UiConfig message, used by VideoConfiguration.ui_config in
 * service discovery and as the nested value of update request/reply bodies. */
unsigned i30_uiconfig_encode_ui(uint8_t *out, unsigned capacity, const I30UiConfig *config);

/* message_id is the big-endian media message ID: 0x8009 for the head unit's
 * UPDATE_UI_CONFIG_REQUEST or 0x800A for the phone's reply. The body follows
 * UpdateUiConfigRequest/UpdateUiConfigReply: field 1 is a UiConfig message. */
unsigned i30_uiconfig_encode(uint8_t *out, unsigned capacity, unsigned message_id,
                             const I30UiConfig *config);

/* Decode only the protobuf body (without the two-byte message ID). Returns 1
 * for a well-formed message and sets I30_UI_CONFIG_* bits in config->present. */
int i30_uiconfig_decode(const uint8_t *body, unsigned length, I30UiConfig *config);

/* Build the compile-time experimental configuration from the macros below. */
void i30_uiconfig_experiment_default(I30UiConfig *config);

/* Build-time inputs. Zero means "do not propose a layout change"; no
 * TMAP-specific geometry or non-zero default is encoded in the stable image. */
#ifndef I30_UI_CONFIG_PRESENT
#define I30_UI_CONFIG_PRESENT (I30_UI_CONFIG_CONTENT | I30_UI_CONFIG_STABLE)
#endif
#ifndef I30_UI_CONFIG_MARGINS_TOP
#define I30_UI_CONFIG_MARGINS_TOP 0U
#endif
#ifndef I30_UI_CONFIG_MARGINS_BOTTOM
#define I30_UI_CONFIG_MARGINS_BOTTOM 0U
#endif
#ifndef I30_UI_CONFIG_MARGINS_LEFT
#define I30_UI_CONFIG_MARGINS_LEFT 0U
#endif
#ifndef I30_UI_CONFIG_MARGINS_RIGHT
#define I30_UI_CONFIG_MARGINS_RIGHT 0U
#endif
#ifndef I30_UI_CONFIG_CONTENT_TOP
#define I30_UI_CONFIG_CONTENT_TOP 0U
#endif
#ifndef I30_UI_CONFIG_CONTENT_BOTTOM
#define I30_UI_CONFIG_CONTENT_BOTTOM 0U
#endif
#ifndef I30_UI_CONFIG_CONTENT_LEFT
#define I30_UI_CONFIG_CONTENT_LEFT 0U
#endif
#ifndef I30_UI_CONFIG_CONTENT_RIGHT
#define I30_UI_CONFIG_CONTENT_RIGHT 0U
#endif
#ifndef I30_UI_CONFIG_STABLE_TOP
#define I30_UI_CONFIG_STABLE_TOP 0U
#endif
#ifndef I30_UI_CONFIG_STABLE_BOTTOM
#define I30_UI_CONFIG_STABLE_BOTTOM 0U
#endif
#ifndef I30_UI_CONFIG_STABLE_LEFT
#define I30_UI_CONFIG_STABLE_LEFT 0U
#endif
#ifndef I30_UI_CONFIG_STABLE_RIGHT
#define I30_UI_CONFIG_STABLE_RIGHT 0U
#endif

#endif
