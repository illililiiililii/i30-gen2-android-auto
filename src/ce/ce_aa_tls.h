#ifndef I30_CE_AA_TLS_H
#define I30_CE_AA_TLS_H

#include "aa_wire.h"

enum I30AuthResult { I30_AUTH_ENDED, I30_AUTH_CONFIG, I30_AUTH_PHONE_REFUSED,
                     I30_AUTH_FAILED, I30_AUTH_MEDIA_FAILED };

/* The caller owns the USB pipes and starts a separate budget for video. */
enum I30AuthResult i30_ce_authenticate(const I30Link *link, void (*start_video)(void *context),
                                      void (*video_presented)(void *context));

#endif
