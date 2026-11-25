#ifndef I30_CE_AA_PROJECTION_H
#define I30_CE_AA_PROJECTION_H

#include "ce_minimal.h"
#include "aa_wire.h"

#define I30_PROJECTION_WINDOW_TITLE L"Android Auto · i30"
#define I30_PROJECTION_VIDEO_CHANNEL 3U
#define I30_PROJECTION_INPUT_CHANNEL 1U

typedef struct I30SecureChannel {
    void *context;
    int (*send)(void *context, unsigned channel, unsigned flags, const uint8_t *data, unsigned size);
    /* Complete control messages use receiver-owned storage so partial video stays in video_buffer. */
    int (*receive)(void *context, unsigned *channel, unsigned *flags, uint8_t *video_buffer,
                   unsigned capacity, uint8_t **message, I30ReadPoll poll, void *poll_context);
    void (*presented)(void *context);
} I30SecureChannel;

/* Returns a verified projection target while the stock display permits drawing. */
CE_HANDLE i30_projection_surface(void);
/* Service discovery can bind the native window during a temporary stock overlay. */
CE_HANDLE i30_projection_target(void);
int i30_projection_has_input(CE_HANDLE window);
int i30_projection_video(const I30SecureChannel *transport, CE_HANDLE window, int input);

#endif
