#ifndef I30_CE_AA_PROJECTION_H
#define I30_CE_AA_PROJECTION_H

#include "ce_minimal.h"

#define I30_PROJECTION_WINDOW_TITLE L"Android Auto · i30"

typedef struct I30SecureChannel {
    void *context;
    int (*send)(void *context, unsigned channel, unsigned flags, const uint8_t *data, unsigned size);
    int (*receive)(void *context, unsigned *channel, unsigned *flags, uint8_t *data, unsigned capacity);
} I30SecureChannel;

/* Returns a verified projection target while the stock display permits drawing. */
CE_HANDLE i30_projection_surface(void);
/* Service discovery can bind the native window during a temporary stock overlay. */
CE_HANDLE i30_projection_target(void);
int i30_projection_video(const I30SecureChannel *transport, CE_HANDLE window);

#endif
