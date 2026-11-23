#ifndef I30_CE_AA_TLS_H
#define I30_CE_AA_TLS_H

#include "aa_wire.h"

/* The caller owns the USB pipes and starts a separate budget after video is negotiated. */
/* Returns nonzero when the local head-unit TLS configuration needs attention. */
int i30_ce_authenticate(const I30Link *link, void (*start_video)(void *context));

#endif
