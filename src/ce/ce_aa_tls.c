#include "ce_aa_tls.h"
#include "ce_minimal.h"
#include "ce_aa_usb.h"
#include "bearssl.h"
#ifdef I30_NATIVE_VIDEO
#include "ce_aa_projection.h"
#endif

#include <string.h>

CE_HANDLE LocalAlloc(uint32_t, uint32_t);
CE_HANDLE LocalFree(CE_HANDLE);
uint32_t GetFileAttributesW(const CE_WCHAR *);
int CeGenRandom(uint32_t size, uint8_t *bytes);
void GetSystemTimeAsFileTime(uint64_t *time);

#define TLS_FRAME_MAX 0x4200U
#define TLS_MESSAGE_MAX (2U * 1024U * 1024U)
#define TLS_MESSAGE 3U
#define DISCOVERY_REQUEST 5U
#define BYEBYE_REQUEST 15U
#define FILETIME_EPOCH_DAY 584754U
#define SECONDS_PER_DAY 86400U
#define TLS_PATH L"\\DiskA\\Application\\NAVI\\"
#define CLIENT_CHAIN_MAX 4U

enum { FILE_MISSING = -1, FILE_UNREADABLE = -2, FILE_FORMAT = -3 };

typedef struct PinnedChain {
    const br_x509_class *vtable;
    const br_x509_class **chain;
    br_sha256_context leaf;
    uint8_t expected[32];
    unsigned count;
    int matched, rejected;
} PinnedChain;

typedef struct Credential {
    uint8_t *bytes;
    size_t length, capacity;
    int overflow;
} Credential;

typedef struct ProtectedMessage {
    unsigned used, total, flags;
} ProtectedMessage;

typedef struct HandshakeTrace {
    uint8_t record[5], message[4], certificate[6];
    unsigned record_used, message_used, certificate_used;
    unsigned record_left, message_left, leaf_left;
    int encrypted;
} HandshakeTrace;

typedef struct Session {
    br_ssl_client_context client;
    br_x509_minimal_context validation;
    br_x509_decoder_context cert;
    br_x509_decoder_context client_decoder;
    br_pem_decoder_context pem;
    Credential decoded;
    br_x509_trust_anchor anchor;
    br_skey_decoder_context identity_key;
    br_x509_certificate identity[CLIENT_CHAIN_MAX];
    PinnedChain pinned;
    HandshakeTrace tx, rx;
    br_sha256_context sent_leaf;
    uint8_t io[BR_SSL_BUFSIZE_BIDI];
    uint8_t wire[TLS_FRAME_MAX + 6U];
    uint8_t control[0x4000];
    ProtectedMessage control_rx, video_rx, input_rx;
    uint8_t input[128];
    uint8_t ca[4096], dn[512];
    uint8_t client_cert[8192], key_der[4096];
    uint8_t encoded[12289];
    char peer[256];
    unsigned dn_size, fragment_remaining, message_remaining;
} Session;

typedef struct Der {
    const uint8_t *bytes;
    size_t length;
} Der;

typedef struct Utc {
    uint32_t day, second;
} Utc;

static void pin_start(const br_x509_class **context, const char *name)
{
    PinnedChain *pin = (PinnedChain *)context;
    pin->count = 0;
    pin->matched = 0;
    pin->rejected = 0;
    br_sha256_init(&pin->leaf);
    (*pin->chain)->start_chain(pin->chain, name);
}

static void pin_certificate(const br_x509_class **context, uint32_t length)
{
    PinnedChain *pin = (PinnedChain *)context;
    (*pin->chain)->start_cert(pin->chain, length);
}

static void pin_append(const br_x509_class **context, const uint8_t *bytes, size_t length)
{
    PinnedChain *pin = (PinnedChain *)context;
    if (!pin->count)
        br_sha256_update(&pin->leaf, bytes, length);
    (*pin->chain)->append(pin->chain, bytes, length);
}

static void pin_end_certificate(const br_x509_class **context)
{
    PinnedChain *pin = (PinnedChain *)context;
    if (!pin->count++) {
        uint8_t digest[32];
        unsigned difference = 0;
        br_sha256_out(&pin->leaf, digest);
        for (unsigned i = 0; i < sizeof(digest); ++i)
            difference |= digest[i] ^ pin->expected[i];
        pin->matched = difference == 0;
    }
    (*pin->chain)->end_cert(pin->chain);
}

static unsigned pin_end(const br_x509_class **context)
{
    PinnedChain *pin = (PinnedChain *)context;
    unsigned result = (*pin->chain)->end_chain(pin->chain);
    pin->rejected = !result && !pin->matched;
    return pin->rejected ? BR_ERR_X509_NOT_TRUSTED : result;
}

static const br_x509_pkey *pin_key(const br_x509_class *const *context, unsigned *uses)
{
    const PinnedChain *pin = (const PinnedChain *)context;
    return (*pin->chain)->get_pkey(pin->chain, uses);
}

static const br_x509_class pinned_chain = {
    sizeof(PinnedChain), pin_start, pin_certificate, pin_append, pin_end_certificate, pin_end, pin_key
};

static unsigned read_bounded(CE_HANDLE file, void *bytes, unsigned capacity)
{
    uint32_t length = 0, end = 0;
    uint8_t surplus;
    if (!ReadFile(file, bytes, capacity, &length, 0) ||
        !ReadFile(file, &surplus, 1, &end, 0) || end)
        length = 0;
    CloseHandle(file);
    return length;
}

static unsigned bounded_file(const CE_WCHAR *path, void *bytes, unsigned capacity)
{
    CE_HANDLE file = CreateFileW(path, 0x80000000U, 1, 0, 3, 0x80, 0);
    return file == (CE_HANDLE)-1 ? 0 : read_bounded(file, bytes, capacity);
}

static void append_credential(void *context, const void *data, size_t length)
{
    Credential *out = context;
    if (length > out->capacity - out->length) {
        out->overflow = 1;
        return;
    }
    memcpy(out->bytes + out->length, data, length);
    out->length += length;
}

static int missing_file(uint32_t error)
{
    return error == 2U || error == 3U; /* ERROR_FILE_NOT_FOUND or ERROR_PATH_NOT_FOUND */
}

static CE_HANDLE open_credential(const CE_WCHAR *der, const CE_WCHAR *pem)
{
    CE_HANDLE file = CreateFileW(der, 0x80000000U, 1, 0, 3, 0x80, 0);
    if (file == (CE_HANDLE)-1 && missing_file(GetLastError()))
        file = CreateFileW(pem, 0x80000000U, 1, 0, 3, 0x80, 0);
    return file;
}

static int decode_credentials(Session *s, CE_HANDLE file, uint8_t *bytes, size_t capacity,
                              br_x509_certificate *objects, unsigned limit, int private_key)
{
    unsigned length = read_bounded(file, s->encoded, sizeof(s->encoded) - 1U);
    if (!length)
        return FILE_UNREADABLE;
    if (s->encoded[0] == 0x30) {
        if (length > capacity)
            return FILE_FORMAT;
        memcpy(bytes, s->encoded, length);
        objects[0] = (br_x509_certificate){bytes, length};
        return 1;
    }
    s->decoded = (Credential){bytes, 0, capacity, 0};
    unsigned count = 0;
    int open = 0;
    s->encoded[length++] = '\n';
    br_pem_decoder_init(&s->pem);
    for (unsigned offset = 0; offset < length;) {
        size_t consumed = br_pem_decoder_push(&s->pem, s->encoded + offset, length - offset);
        int event = br_pem_decoder_event(&s->pem);
        if (event == BR_PEM_BEGIN_OBJ) {
            const char *name = br_pem_decoder_name(&s->pem);
            if (open || count == limit ||
                (private_key ? (strcmp(name, "PRIVATE KEY") && strcmp(name, "RSA PRIVATE KEY"))
                             : strcmp(name, "CERTIFICATE")))
                return FILE_FORMAT;
            objects[count].data = bytes + s->decoded.length;
            open = 1;
            br_pem_decoder_setdest(&s->pem, append_credential, &s->decoded);
        } else if (event == BR_PEM_END_OBJ) {
            if (!open || s->decoded.overflow || objects[count].data == bytes + s->decoded.length)
                return FILE_FORMAT;
            objects[count].data_len = (size_t)(bytes + s->decoded.length - objects[count].data);
            ++count;
            open = 0;
        } else if (event == BR_PEM_ERROR || !consumed) {
            return FILE_FORMAT;
        }
        offset += (unsigned)consumed;
    }
    return open || !count ? FILE_FORMAT : (int)count;
}

static int read_credentials(Session *s, const CE_WCHAR *der, const CE_WCHAR *pem,
                            uint8_t *bytes, size_t capacity, br_x509_certificate *objects,
                            unsigned limit, int private_key)
{
    CE_HANDLE file = open_credential(der, pem);
    if (file == (CE_HANDLE)-1)
        return missing_file(GetLastError()) ? FILE_MISSING : FILE_UNREADABLE;
    return decode_credentials(s, file, bytes, capacity, objects, limit, private_key);
}

static int der_read(Der *source, uint8_t tag, Der *field)
{
    if (source->length < 2 || source->bytes[0] != tag)
        return 0;
    size_t length = source->bytes[1], header = 2;
    if (length >= 128) {
        unsigned count = (unsigned)length & 127U;
        if (!count || count > 2 || count > source->length - header || !source->bytes[header])
            return 0;
        length = 0;
        while (count--)
            length = (length << 8) | source->bytes[header++];
        if (length < 128)
            return 0;
    }
    if (length > source->length - header)
        return 0;
    field->bytes = source->bytes + header;
    field->length = length;
    source->bytes += header + length;
    source->length -= header + length;
    return 1;
}

static unsigned date_number(const uint8_t *text, unsigned length)
{
    unsigned value = 0;
    for (unsigned i = 0; i < length; ++i) {
        if (text[i] < '0' || text[i] > '9')
            return 10000;
        value = 10U * value + text[i] - '0';
    }
    return value;
}

static int der_time(Der *source, Utc *out)
{
    static const uint8_t month_days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (!source->length)
        return 0;
    int short_year = source->bytes[0] == 0x17;
    unsigned year_length = short_year ? 2U : 4U;
    Der field;
    if (!der_read(source, short_year ? 0x17 : 0x18, &field) ||
        field.length != year_length + 11 || field.bytes[field.length - 1] != 'Z')
        return 0;
    unsigned year = date_number(field.bytes, year_length);
    if (year > 9999)
        return 0;
    if (short_year)
        year += year < 50 ? 2000U : 1900U;
    const uint8_t *days = field.bytes + year_length;
    unsigned month = date_number(days, 2), day = date_number(days + 2, 2);
    unsigned h = date_number(days + 4, 2), m = date_number(days + 6, 2), sec = date_number(days + 8, 2);
    int leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    if (!month || month > 12 || !day || day > month_days[month - 1U] + (unsigned)(month == 2 && leap) ||
        h >= 24 || m >= 60 || sec >= 60)
        return 0;
    out->day = year * 365U + (year + 3U) / 4U - (year + 99U) / 100U + (year + 399U) / 400U;
    for (unsigned i = 1; i < month; ++i)
        out->day += month_days[i - 1U];
    out->day += day - 1U + (unsigned)(month > 2 && leap);
    out->second = h * 3600U + m * 60U + sec;
    return 1;
}

static int utc_before(Utc first, Utc second)
{
    return first.day < second.day || (first.day == second.day && first.second < second.second);
}

static int client_validity(const br_x509_certificate *cert, Utc *start, Utc *end)
{
    Der input = {cert->data, cert->data_len}, outer, tbs, field, validity;
    if (!der_read(&input, 0x30, &outer) || input.length || !der_read(&outer, 0x30, &tbs))
        return 0;
    if (tbs.length && tbs.bytes[0] == 0xa0 && !der_read(&tbs, 0xa0, &field))
        return 0;
    return der_read(&tbs, 2, &field) && der_read(&tbs, 0x30, &field) && der_read(&tbs, 0x30, &field) &&
           der_read(&tbs, 0x30, &validity) && der_time(&validity, start) && der_time(&validity, end) &&
           !validity.length && !utc_before(*end, *start);
}

static int matches_key(const br_rsa_public_key *public_key, const br_rsa_private_key *private_key, Der encoded)
{
    uint8_t modulus[512];
    Der sequence, field, wrapped, exponent;
    br_rsa_compute_modulus compute_modulus = br_rsa_compute_modulus_get_default();
    if (!der_read(&encoded, 0x30, &sequence) || encoded.length || !der_read(&sequence, 2, &field))
        return 0;
    if (sequence.length && sequence.bytes[0] == 0x30) {
        /* PKCS#8 wraps the PKCS#1 RSA key in an OCTET STRING. */
        if (!der_read(&sequence, 0x30, &field) || !der_read(&sequence, 4, &wrapped) ||
            !der_read(&wrapped, 0x30, &sequence) || wrapped.length || !der_read(&sequence, 2, &field))
            return 0;
    }
    if (!der_read(&sequence, 2, &field) || !der_read(&sequence, 2, &exponent) || !compute_modulus)
        return 0;
    if (exponent.length > 1 && !exponent.bytes[0]) {
        ++exponent.bytes;
        --exponent.length;
    }
    size_t length = compute_modulus(0, private_key);
    return length && length <= sizeof(modulus) && length == public_key->nlen &&
           exponent.length == public_key->elen && !memcmp(exponent.bytes, public_key->e, exponent.length) &&
           compute_modulus(modulus, private_key) == length && !memcmp(modulus, public_key->n, length);
}

static void debug_number(const CE_WCHAR *label, uint32_t value)
{
    CE_WCHAR line[96];
    unsigned length = 0, digits = 0;
    char reverse[10];
    while (*label && length < 82)
        line[length++] = *label++;
    do {
        reverse[digits++] = '0' + value % 10U;
        value /= 10U;
    } while (value);
    while (digits)
        line[length++] = (CE_WCHAR)reverse[--digits];
    line[length++] = '\r';
    line[length++] = '\n';
    line[length] = 0;
    OutputDebugStringW(line);
}

static void debug_fingerprint(const CE_WCHAR *label, const uint8_t *digest)
{
    static const char hex[] = "0123456789abcdef";
    CE_WCHAR line[128];
    unsigned length = 0;
    while (*label)
        line[length++] = *label++;
    for (unsigned i = 0; i < 32; ++i) {
        line[length++] = hex[digest[i] >> 4];
        line[length++] = hex[digest[i] & 15U];
    }
    line[length++] = '\r';
    line[length++] = '\n';
    line[length] = 0;
    OutputDebugStringW(line);
}

static void debug_file_error(int result)
{
    OutputDebugStringW(result == FILE_MISSING ? L"i30 CE TLS credential file missing.\r\n" :
                       result == FILE_UNREADABLE ? L"i30 CE TLS credential file empty, unreadable or oversized.\r\n" :
                       L"i30 CE TLS credential file format invalid.\r\n");
}

static unsigned big_endian(const uint8_t *bytes, unsigned size)
{
    unsigned value = 0;
    while (size--)
        value = (value << 8) | *bytes++;
    return value;
}

static void trace_certificate(Session *s, HandshakeTrace *trace, const uint8_t *bytes, unsigned size)
{
    while (size && trace->certificate_used < sizeof(trace->certificate)) {
        trace->certificate[trace->certificate_used++] = *bytes++;
        --size;
        if (trace->certificate_used == sizeof(trace->certificate)) {
            unsigned list_size = big_endian(trace->certificate, 3);
            unsigned leaf_size = big_endian(trace->certificate + 3, 3);
            if (list_size >= 3 && leaf_size <= list_size - 3)
                trace->leaf_left = leaf_size;
            br_sha256_init(&s->sent_leaf);
        }
    }
    if (trace->leaf_left && size) {
        if (size > trace->leaf_left)
            size = trace->leaf_left;
        br_sha256_update(&s->sent_leaf, bytes, size);
        trace->leaf_left -= size;
        if (!trace->leaf_left) {
            uint8_t digest[32];
            br_sha256_out(&s->sent_leaf, digest);
            debug_fingerprint(L"i30 CE TLS sent leaf SHA-256: ", digest);
        }
    }
}

/* Observe completed plaintext handshake messages across TLS record boundaries.
   BearSSL handles validation and authenticates the encrypted Finished messages. */
static void trace_handshake(Session *s, HandshakeTrace *trace, const uint8_t *bytes, unsigned size)
{
    while (size) {
        if (trace->message_used < sizeof(trace->message)) {
            trace->message[trace->message_used++] = *bytes++;
            --size;
            if (trace->message_used < sizeof(trace->message))
                continue;
            trace->message_left = big_endian(trace->message + 1, 3);
            trace->certificate_used = trace->leaf_left = 0;
        }
        unsigned take = size < trace->message_left ? size : trace->message_left;
        unsigned type = trace->message[0];
        if (trace == &s->tx && type == 11U)
            trace_certificate(s, trace, bytes, take);
        bytes += take;
        size -= take;
        trace->message_left -= take;
        if (!trace->message_left) {
            trace->message_used = 0;
            debug_number(trace == &s->tx ? L"i30 CE TLS handshake message sent: " :
                         L"i30 CE TLS handshake message received: ", type);
            if (trace == &s->tx && type == 1U)
                OutputDebugStringW(L"i30 CE TLS ClientHello sent.\r\n");
        }
    }
}

static void trace_records(Session *s, HandshakeTrace *trace, const uint8_t *bytes, unsigned size)
{
    while (size && !trace->encrypted) {
        if (trace->record_used < sizeof(trace->record)) {
            trace->record[trace->record_used++] = *bytes++;
            --size;
            if (trace->record_used < sizeof(trace->record))
                continue;
            trace->record_left = big_endian(trace->record + 3, 2);
        }
        unsigned take = size < trace->record_left ? size : trace->record_left;
        if (trace->record[0] == 22U)
            trace_handshake(s, trace, bytes, take);
        bytes += take;
        size -= take;
        trace->record_left -= take;
        if (!trace->record_left) {
            trace->record_used = 0;
            if (trace->record[0] == 20U) {
                trace->encrypted = 1;
                OutputDebugStringW(trace == &s->tx ? L"i30 CE TLS ChangeCipherSpec sent.\r\n" :
                                   L"i30 CE TLS ChangeCipherSpec received.\r\n");
            }
        }
    }
}

static int read_utc(Utc *utc)
{
    uint64_t filetime = 0;
    GetSystemTimeAsFileTime(&filetime);
    uint64_t seconds = filetime / 10000000U;
    utc->day = (uint32_t)(seconds / SECONDS_PER_DAY) + FILETIME_EPOCH_DAY;
    utc->second = (uint32_t)(seconds % SECONDS_PER_DAY);
    debug_number(L"i30 CE TLS clock UTC day since 0000-01-01: ", utc->day);
    debug_number(L"i30 CE TLS clock UTC second of day: ", utc->second);
    /* This firmware is newer than 2000. Reject an unset or out-of-range clock. */
    return utc->day >= 730485U && utc->day < 3652425U;
}

static void append_dn(void *context, const void *data, size_t count)
{
    Session *s = context;
    if (s->dn_size > sizeof(s->dn) || count > sizeof(s->dn) - s->dn_size) {
        s->dn_size = sizeof(s->dn) + 1U;
        return;
    }
    memcpy(s->dn + s->dn_size, data, count);
    s->dn_size += count;
}

static unsigned trim_line(const char *data, unsigned size)
{
    while (size && (data[size - 1U] == '\r' || data[size - 1U] == '\n'))
        --size;
    return size;
}

static int digit(unsigned c)
{
    if (c >= '0' && c <= '9')
        return (int)(c - '0');
    c |= 32;
    return c >= 'a' && c <= 'f' ? (int)(c - 'a') + 10 : -1;
}

static int parse_pin(uint8_t *digest, const char *text, unsigned size)
{
    if (size != 64)
        return 0;
    for (unsigned i = 0; i < 32; ++i) {
        int high = digit((uint8_t)text[2 * i]), low = digit((uint8_t)text[2 * i + 1]);
        if (high < 0 || low < 0)
            return 0;
        digest[i] = (uint8_t)((high << 4) | low);
    }
    return 1;
}

static int client_chain_valid(Session *s, unsigned count, Utc now)
{
    br_x509_trust_anchor issuer;
    Utc start, end;
    for (unsigned i = 1; i < count; ++i) {
        const br_x509_certificate *cert = &s->identity[i];
        if (!client_validity(cert, &start, &end) || utc_before(now, start) || utc_before(end, now)) {
            debug_number(L"i30 CE TLS issuer validity rejected at chain index: ", i);
            return 0;
        }
        s->dn_size = 0;
        br_x509_decoder_init(&s->client_decoder, append_dn, s);
        br_x509_decoder_push(&s->client_decoder, cert->data, cert->data_len);
        const br_x509_pkey *key = br_x509_decoder_get_pkey(&s->client_decoder);
        if (!key || !br_x509_decoder_isCA(&s->client_decoder) || !s->dn_size || s->dn_size > sizeof(s->dn)) {
            debug_number(L"i30 CE TLS issuer certificate rejected at chain index: ", i);
            debug_number(L"i30 CE TLS issuer decoder result: ", br_x509_decoder_last_error(&s->client_decoder));
            return 0;
        }
        issuer = (br_x509_trust_anchor){{s->dn, s->dn_size}, BR_X509_TA_CA, *key};
        /* Check every prefix against its next issuer, using only the supplied chain.
           The remote peer still decides whether the chain ends at a trusted root. */
        br_x509_minimal_init_full(&s->validation, &issuer, 1);
        br_x509_minimal_set_time(&s->validation, now.day, now.second);
        const br_x509_class **validator = &s->validation.vtable;
        (*validator)->start_chain(validator, 0);
        for (unsigned j = 0; j < i; ++j) {
            const br_x509_certificate *member = &s->identity[j];
            (*validator)->start_cert(validator, (uint32_t)member->data_len);
            (*validator)->append(validator, member->data, member->data_len);
            (*validator)->end_cert(validator);
        }
        unsigned error = (*validator)->end_chain(validator);
        if (error) {
            debug_number(L"i30 CE TLS supplied client chain validation error: ", error);
            return 0;
        }
    }
    return 1;
}

static const CE_WCHAR *configure(Session *s, CE_HANDLE ca_file, int aare)
{
    uint8_t seed[32], digest[32];
    br_sha256_context hash;
    char pin[67];
    Utc now, start, end;
    unsigned name_size, pin_size;
    br_x509_certificate ca, key_file;
    const br_x509_pkey *key;
    const br_rsa_private_key *client_key;
    int result = decode_credentials(s, ca_file, s->ca, sizeof(s->ca), &ca, 1, 0);
    if (result < 0) {
        debug_file_error(result);
        return L"i30 CE TLS trust CA missing, unreadable or invalid.\r\n";
    }
    if (!read_utc(&now))
        return L"i30 CE TLS guest UTC unavailable or invalid.\r\n";
    name_size = aare ? 0U : bounded_file(TLS_PATH L"i30-peer.txt", s->peer, sizeof(s->peer) - 1U);
    pin_size = bounded_file(aare ? TLS_PATH L"i30-aare-peer-sha256.txt" : TLS_PATH L"i30-peer-sha256.txt",
                            pin, sizeof(pin));
    name_size = trim_line(s->peer, name_size);
    pin_size = trim_line(pin, pin_size);
    if ((name_size != 0) == (pin_size != 0) ||
        (pin_size && !parse_pin(s->pinned.expected, pin, pin_size)))
        return L"i30 CE TLS peer hostname or fingerprint configuration invalid.\r\n";
    for (unsigned i = 0; i < name_size; ++i) {
        unsigned c = (uint8_t)s->peer[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '.' || c == '-'))
            return L"i30 CE TLS peer hostname or fingerprint configuration invalid.\r\n";
    }
    s->peer[name_size] = '\0';
    int identity_count = read_credentials(s, aare ? TLS_PATH L"i30-aare-client.der" : TLS_PATH L"i30-client.der",
                                          aare ? TLS_PATH L"i30-aare-client.pem" : TLS_PATH L"i30-client.pem",
                                          s->client_cert, sizeof(s->client_cert), s->identity, CLIENT_CHAIN_MAX, 0);
    if (identity_count < 0) {
        debug_file_error(identity_count);
        return L"i30 CE TLS head unit certificate missing, unreadable or invalid.\r\n";
    }
    br_sha256_init(&hash);
    br_sha256_update(&hash, s->identity[0].data, s->identity[0].data_len);
    br_sha256_out(&hash, digest);
    debug_fingerprint(L"i30 CE TLS loaded leaf SHA-256: ", digest);
    br_x509_decoder_init(&s->client_decoder, 0, 0);
    br_x509_decoder_push(&s->client_decoder, s->identity[0].data, s->identity[0].data_len);
    debug_number(L"i30 CE TLS head unit certificate decoder result: ", br_x509_decoder_last_error(&s->client_decoder));
    key = br_x509_decoder_get_pkey(&s->client_decoder);
    if (!key || key->key_type != BR_KEYTYPE_RSA)
        return L"i30 CE TLS head unit certificate missing, unreadable or invalid.\r\n";
    if (!client_validity(&s->identity[0], &start, &end))
        return L"i30 CE TLS head unit certificate validity field invalid.\r\n";
    if (utc_before(now, start))
        return L"i30 CE TLS head unit certificate is not yet valid at guest UTC.\r\n";
    if (utc_before(end, now))
        return L"i30 CE TLS head unit certificate expired at guest UTC.\r\n";
    result = read_credentials(s, aare ? TLS_PATH L"i30-aare-client-key.der" : TLS_PATH L"i30-client-key.der",
                              aare ? TLS_PATH L"i30-aare-client-key.pem" : TLS_PATH L"i30-client-key.pem",
                              s->key_der, sizeof(s->key_der), &key_file, 1, 1);
    if (result < 0) {
        debug_file_error(result);
        return L"i30 CE TLS head unit RSA key missing, unreadable or invalid.\r\n";
    }
    br_skey_decoder_init(&s->identity_key);
    br_skey_decoder_push(&s->identity_key, key_file.data, key_file.data_len);
    client_key = br_skey_decoder_get_rsa(&s->identity_key);
    if (!client_key)
        return L"i30 CE TLS head unit RSA key missing, unreadable or invalid.\r\n";
    if (!matches_key(&key->key.rsa, client_key, (Der){key_file.data, key_file.data_len}))
        return L"i30 CE TLS head unit certificate and RSA key do not match.\r\n";
    if (!client_chain_valid(s, (unsigned)identity_count, now))
        return L"i30 CE TLS head unit certificate chain invalid.\r\n";
    s->dn_size = 0;
    br_x509_decoder_init(&s->cert, append_dn, s);
    br_x509_decoder_push(&s->cert, ca.data, ca.data_len);
    debug_number(L"i30 CE TLS trust CA decoder result: ", br_x509_decoder_last_error(&s->cert));
    key = br_x509_decoder_get_pkey(&s->cert);
    Der ca_der = {ca.data, ca.data_len}, ca_sequence;
    if (!key || !br_x509_decoder_isCA(&s->cert) || !s->dn_size || s->dn_size > sizeof(s->dn) ||
        !der_read(&ca_der, 0x30, &ca_sequence) || ca_der.length)
        return L"i30 CE TLS trust CA missing, unreadable or invalid.\r\n";
    s->anchor = (br_x509_trust_anchor){{s->dn, s->dn_size}, BR_X509_TA_CA, *key};
    br_ssl_client_init_full(&s->client, &s->validation, &s->anchor, 1);
    if (pin_size) {
        s->pinned.vtable = &pinned_chain;
        s->pinned.chain = &s->validation.vtable;
        br_ssl_engine_set_x509(&s->client.eng, &s->pinned.vtable);
    }
    br_ssl_client_set_single_rsa(&s->client, s->identity, (unsigned)identity_count, client_key,
                                 br_rsa_pkcs1_sign_get_default());
    br_ssl_engine_set_versions(&s->client.eng, BR_TLS12, BR_TLS12);
    br_ssl_engine_set_buffer(&s->client.eng, s->io, sizeof(s->io), 1);
    br_x509_minimal_set_time(&s->validation, now.day, now.second);
    if (!CeGenRandom(sizeof(seed), seed))
        return L"i30 CE TLS secure randomness unavailable.\r\n";
    br_ssl_engine_inject_entropy(&s->client.eng, seed, sizeof(seed));
    for (unsigned i = 0; i < sizeof(seed); ++i)
        ((volatile uint8_t *)seed)[i] = 0;
    if (!br_ssl_client_reset(&s->client, pin_size ? 0 : s->peer, 0)) {
        debug_number(L"i30 CE TLS BearSSL error: ", br_ssl_engine_last_error(&s->client.eng));
        return L"i30 CE TLS client initialization failed.\r\n";
    }
    return 0;
}

static int read_exact(const I30Link *link, uint8_t *bytes, unsigned length)
{
    while (length) {
        int read = link->read(link->context, bytes, length);
        if (read <= 0 || (unsigned)read > length)
            return 0;
        bytes += read;
        length -= (unsigned)read;
    }
    return 1;
}

static int send_record(Session *s, const I30Link *link, const uint8_t *data, size_t length)
{
    unsigned size = (unsigned)length + 2U;
    if (!length || size > TLS_FRAME_MAX)
        return 0;
    s->wire[0] = 0;
    s->wire[1] = 3; /* First and last, plaintext control channel. */
    s->wire[2] = (uint8_t)(size >> 8);
    s->wire[3] = (uint8_t)size;
    s->wire[4] = 0;
    s->wire[5] = TLS_MESSAGE;
    memcpy(s->wire + 6, data, length);
    return link->write(link->context, s->wire, size + 4U) == (int)(size + 4U);
}

static int receive_handshake_frame(Session *s, const I30Link *link, int first)
{
    uint8_t header[4];
    if (!read_exact(link, header, sizeof(header)))
        return 0;
    unsigned flags = header[1], size = ((unsigned)header[2] << 8) | header[3];
    if (header[0] || flags > 3U || ((flags & 1U) != 0) != first || !size || size > TLS_FRAME_MAX)
        return -1;
    if (first) {
        unsigned total = size;
        if (!(flags & 2U)) {
            if (!read_exact(link, header, sizeof(header)))
                return 0;
            total = ((unsigned)header[0] << 24) | ((unsigned)header[1] << 16) |
                    ((unsigned)header[2] << 8) | header[3];
            if (total <= size)
                return -1;
        }
        if (total <= 2U || total > TLS_MESSAGE_MAX)
            return -1;
        s->message_remaining = total;
    }
    if (size > s->message_remaining || ((flags & 2U) != 0) != (size == s->message_remaining))
        return -1;
    s->message_remaining -= size;
    s->fragment_remaining = size;
    return 1;
}

static int receive_record(Session *s, const I30Link *link, uint8_t *data, size_t capacity)
{
    if (!s->fragment_remaining) {
        int first = !s->message_remaining;
        int status = receive_handshake_frame(s, link, first);
        if (status <= 0)
            return status;
        if (first) {
            /* Only the logical message starts with a message ID. It can span fragments. */
            uint8_t code[2];
            for (unsigned i = 0; i < sizeof(code); ++i) {
                if (!s->fragment_remaining) {
                    status = receive_handshake_frame(s, link, 0);
                    if (status <= 0)
                        return status;
                }
                if (!read_exact(link, code + i, 1))
                    return 0;
                --s->fragment_remaining;
            }
            if (code[0] || code[1] != TLS_MESSAGE)
                return -1;
            if (!s->fragment_remaining) {
                status = receive_handshake_frame(s, link, 0);
                if (status <= 0)
                    return status;
            }
        }
    }
    if (capacity > s->fragment_remaining)
        capacity = s->fragment_remaining;
    if (!capacity || !read_exact(link, data, (unsigned)capacity))
        return 0;
    s->fragment_remaining -= (unsigned)capacity;
    return (int)capacity;
}

static int secure_write(Session *s, const I30Link *link, unsigned channel, unsigned flags,
                        const uint8_t *message, unsigned length)
{
    br_ssl_engine_context *engine = &s->client.eng;
    size_t capacity;
    uint8_t *app = br_ssl_engine_sendapp_buf(engine, &capacity);
    if (!app || length > capacity)
        return 0;
    memcpy(app, message, length);
    br_ssl_engine_sendapp_ack(engine, length);
    br_ssl_engine_flush(engine, 0);
    uint8_t *record = br_ssl_engine_sendrec_buf(engine, &capacity);
    if (!record || !capacity || capacity > TLS_FRAME_MAX)
        return 0;
    s->wire[0] = (uint8_t)channel;
    s->wire[1] = (uint8_t)(11U | flags); /* First, last and encrypted. */
    s->wire[2] = (uint8_t)(capacity >> 8);
    s->wire[3] = (uint8_t)capacity;
    memcpy(s->wire + 4, record, capacity);
    if (link->write(link->context, s->wire, (unsigned)capacity + 4U) != (int)capacity + 4)
        return 0;
    br_ssl_engine_sendrec_ack(engine, capacity);
    return br_ssl_engine_last_error(engine) == 0;
}

static int secure_read_fragment(Session *s, const I30Link *link, unsigned *channel, unsigned *flags,
                                unsigned *total, I30ReadPoll poll, void *poll_context)
{
    br_ssl_engine_context *engine = &s->client.eng;
    uint8_t header[4];
    unsigned length, decoded = 0;
    size_t capacity;
    if (poll && link->poll_read)
        link->poll_read(link->context, poll, poll_context);
    int received = read_exact(link, header, sizeof(header));
    if (poll && link->poll_read)
        link->poll_read(link->context, 0, 0);
    if (!received || (header[1] & 0xf8U) != 8U)
        return -1;
    *channel = header[0];
    *flags = header[1] & 7U;
    length = ((unsigned)header[2] << 8) | header[3];
    if (!length || length > TLS_FRAME_MAX)
        return -1;
    *total = 0;
    if ((*flags & 3U) == 1U) {
        if (!read_exact(link, header, sizeof(header)))
            return -1;
        *total = ((unsigned)header[0] << 24) | ((unsigned)header[1] << 16) |
                 ((unsigned)header[2] << 8) | header[3];
        if (*total < 2U)
            return -1;
    }
    while (length) {
        uint8_t *record = br_ssl_engine_recvrec_buf(engine, &capacity);
        if (!record || !capacity)
            return -1;
        if (capacity > length)
            capacity = length;
        if (!read_exact(link, record, (unsigned)capacity))
            return -1;
        br_ssl_engine_recvrec_ack(engine, capacity);
        length -= (unsigned)capacity;
        uint8_t *app = br_ssl_engine_recvapp_buf(engine, &capacity);
        if (app) {
            if (capacity > sizeof(s->wire) - decoded)
                return -1;
            memcpy(s->wire + decoded, app, capacity);
            decoded += capacity;
            br_ssl_engine_recvapp_ack(engine, capacity);
        }
    }
    if (!decoded || br_ssl_engine_last_error(engine))
        return -1;
    return (int)decoded;
}

static int secure_read(Session *s, const I30Link *link, unsigned *channel, unsigned *flags,
                       uint8_t *video_buffer, unsigned video_capacity, uint8_t **message,
                       I30ReadPoll poll, void *poll_context)
{
#ifndef I30_NATIVE_VIDEO
    (void)video_buffer;
    (void)video_capacity;
#endif
    for (;;) {
        unsigned raw, total;
        int size = secure_read_fragment(s, link, channel, &raw, &total, poll, poll_context);
        if (size <= 0)
            return -1;
        ProtectedMessage *pending = &s->control_rx;
        uint8_t *output = s->control;
        unsigned limit = sizeof(s->control);
        if (*channel != 0) {
#ifdef I30_NATIVE_VIDEO
            if (!video_buffer)
                return -1;
            if (*channel == I30_PROJECTION_VIDEO_CHANNEL) {
                pending = &s->video_rx;
                output = video_buffer;
                limit = video_capacity;
            } else if (*channel == I30_PROJECTION_INPUT_CHANNEL) {
                pending = &s->input_rx;
                output = s->input;
                limit = sizeof(s->input);
            } else {
                return -1;
            }
#else
            return -1;
#endif
        }
        int first = (raw & 1U) != 0, last = (raw & 2U) != 0;
        unsigned message_flags = raw & 4U;
        if (first) {
            if (pending->total)
                return -1;
            pending->total = last ? (unsigned)size : total;
            pending->flags = message_flags;
        }
        if (pending->total < 2U || pending->total > limit ||
            pending->flags != message_flags || (unsigned)size > pending->total - pending->used)
            return -1;
        memcpy(output + pending->used, s->wire, (unsigned)size);
        pending->used += (unsigned)size;
        if (last != (pending->used == pending->total))
            return -1;
        if (last) {
            unsigned decoded = pending->used;
            pending->used = pending->total = 0;
            *flags = message_flags;
            *message = output;
            return (int)decoded;
        }
    }
}

#ifdef I30_NATIVE_VIDEO
typedef struct MediaLink {
    Session *session;
    const I30Link *link;
    void (*presented)(void *);
} MediaLink;

static int send_media(void *context, unsigned channel, unsigned flags, const uint8_t *message, unsigned length)
{
    MediaLink *media = context;
    return secure_write(media->session, media->link, channel, flags, message, length);
}

static int receive_media(void *context, unsigned *channel, unsigned *flags, uint8_t *video_buffer,
                         unsigned capacity, uint8_t **message, I30ReadPoll poll, void *poll_context)
{
    MediaLink *media = context;
    return secure_read(media->session, media->link, channel, flags, video_buffer, capacity, message, poll, poll_context);
}

static void present_media(void *context)
{
    MediaLink *media = context;
    media->presented(media->link->context);
}
#endif

static int discover(Session *s, const I30Link *link, void (*start_video)(void *),
                    void (*video_presented)(void *))
{
    static const uint8_t verified[] = {0, 3, 0, 4, 0, 4, 8, 0}; /* AuthResponse(status=0). */
    /* ServiceDiscoveryResponse with GD13MY identity and no advertised media channels. */
    static const uint8_t identity[] = {0, 6, 0x72, 3, 'i', '3', '0', 0x8a, 1, 25,
        0x2a, 7, 'H', 'y', 'u', 'n', 'd', 'a', 'i', 0x32, 6, 'G', 'D', '1', '3', 'M', 'Y',
        0x42, 6, '0', '0', '.', '0', '6', '1'};
    static const uint8_t disconnect[] = {0, BYEBYE_REQUEST, 8, 1};
    unsigned channel, flags;
    uint8_t *message;
    if (link->write(link->context, verified, sizeof(verified)) != (int)sizeof(verified))
        return 0;
    OutputDebugStringW(L"i30 CE Android Auto AUTH_COMPLETE sent.\r\n");
    if (secure_read(s, link, &channel, &flags, 0, 0, &message, 0, 0) < 2 ||
        channel || flags || message[0] || message[1] != DISCOVERY_REQUEST)
        return 0;
    OutputDebugStringW(L"i30 CE Android Auto encrypted service discovery request received.\r\n");
#ifdef I30_NATIVE_VIDEO
    CE_HANDLE surface = i30_projection_target();
    if (surface) {
        static const uint8_t video_channel[] = {0x0a, 0x0f, 8, 3, 0x1a, 11, 8, 3,
            0x22, 7, 8, 1, 16, 2, 40, 0xa0, 1};
        static const uint8_t input_channel[] = {0x0a, 12, 8, 1, 0x22, 8, 0x12, 6,
            8, 0xa0, 6, 16, 0xe0, 3}; /* TouchScreen 800 x 480, no key codes. */
        const int input = i30_projection_has_input(surface);
        unsigned end = sizeof(identity);
        s->control[0] = 0;
        s->control[1] = 6;
        memcpy(s->control + 2, identity + 2, sizeof(identity) - 2);
        memcpy(s->control + end, video_channel, sizeof(video_channel));
        end += sizeof(video_channel);
        if (input) {
            memcpy(s->control + end, input_channel, sizeof(input_channel));
            end += sizeof(input_channel);
        }
        if (!secure_write(s, link, 0, 0, s->control, end))
            return 0;
        OutputDebugStringW(L"i30 CE authenticated service discovery completed.\r\n");
        start_video(link->context);
        MediaLink media = {s, link, video_presented};
        I30SecureChannel transport = {&media, send_media, receive_media, present_media};
        if (!i30_projection_video(&transport, surface, input))
            OutputDebugStringW(L"i30 CE projection released the display.\r\n");
        return 1;
    }
#endif
    (void)start_video;
    (void)video_presented;
    if (!secure_write(s, link, 0, 0, identity, sizeof(identity)))
        return 0;
    OutputDebugStringW(L"i30 CE authenticated service discovery completed.\r\n");
    if (secure_write(s, link, 0, 0, disconnect, sizeof(disconnect)))
        secure_read(s, link, &channel, &flags, 0, 0, &message, 0, 0);
    return 1;
}

static const CE_WCHAR *handshake_error(Session *s)
{
    unsigned error = br_ssl_engine_last_error(&s->client.eng);
    debug_number(L"i30 CE TLS BearSSL error: ", error);
    if (error >= BR_ERR_RECV_FATAL_ALERT && error < BR_ERR_SEND_FATAL_ALERT) {
        const unsigned alert = error - BR_ERR_RECV_FATAL_ALERT;
        debug_number(L"i30 CE TLS peer fatal alert: ", alert);
        if (alert == 48) /* TLS unknown_ca */
            return L"i30 CE TLS phone rejected the head unit certificate chain (unknown CA).\r\n";
        return L"i30 CE TLS phone sent a fatal alert.\r\n";
    }
    if (error >= BR_ERR_SEND_FATAL_ALERT)
        debug_number(L"i30 CE TLS local fatal alert: ", error - BR_ERR_SEND_FATAL_ALERT);
    if (error == BR_ERR_X509_EXPIRED || error == BR_ERR_X509_TIME_UNKNOWN)
        return L"i30 CE TLS phone certificate rejected at guest UTC.\r\n";
    if (error == BR_ERR_X509_BAD_SERVER_NAME)
        return L"i30 CE TLS phone certificate hostname does not match.\r\n";
    if (error == BR_ERR_X509_NOT_TRUSTED)
        return s->pinned.rejected ? L"i30 CE TLS phone certificate fingerprint does not match.\r\n" :
            L"i30 CE TLS phone certificate chain has no trusted anchor.\r\n";
    if (error == BR_ERR_BAD_CIPHER_SUITE)
        return L"i30 CE TLS cipher suite rejected.\r\n";
    if (error == BR_ERR_UNEXPECTED)
        return L"i30 CE TLS unexpected handshake record or message.\r\n";
    if (error == BR_ERR_UNSUPPORTED_VERSION || error == BR_ERR_BAD_VERSION)
        return L"i30 CE TLS protocol version rejected.\r\n";
    return L"i30 CE TLS engine stopped during handshake.\r\n";
}

static const CE_WCHAR *handshake(Session *s, const I30Link *link)
{
    br_ssl_engine_context *engine = &s->client.eng;
    int received_tls = 0, negotiated = 0;
    for (unsigned step = 0; step < 256U; ++step) {
        unsigned state = br_ssl_engine_current_state(engine);
        size_t size;
        if (state & BR_SSL_CLOSED)
            return handshake_error(s);
        if (state & BR_SSL_SENDREC) {
            uint8_t *record = br_ssl_engine_sendrec_buf(engine, &size);
            if (!send_record(s, link, record, size))
                return L"i30 CE TLS USB write interrupted.\r\n";
            trace_records(s, &s->tx, record, (unsigned)size);
            br_ssl_engine_sendrec_ack(engine, size);
        } else if (state & BR_SSL_SENDAPP) {
            if (s->fragment_remaining || s->message_remaining)
                return L"i30 CE TLS invalid Android Auto handshake frame.\r\n";
            if (br_ssl_engine_last_error(engine))
                return handshake_error(s);
            debug_number(L"i30 CE TLS 1.2 authenticated; cipher suite (decimal): ", engine->session.cipher_suite);
            return 0;
        } else if (state & BR_SSL_RECVREC) {
            uint8_t *record = br_ssl_engine_recvrec_buf(engine, &size);
            int count = receive_record(s, link, record, size);
            if (count < 0)
                return L"i30 CE TLS invalid Android Auto handshake frame.\r\n";
            if (!count)
                return L"i30 CE TLS USB read interrupted while waiting for the phone.\r\n";
            if (!received_tls) {
                OutputDebugStringW(L"i30 CE TLS first phone record bytes received.\r\n");
                received_tls = 1;
            }
            trace_records(s, &s->rx, record, (unsigned)count);
            br_ssl_engine_recvrec_ack(engine, (size_t)count);
            if (!negotiated && engine->session.cipher_suite) {
                debug_number(L"i30 CE TLS negotiated version (decimal): ", br_ssl_engine_get_version(engine));
                debug_number(L"i30 CE TLS negotiated cipher suite (decimal): ", engine->session.cipher_suite);
                negotiated = 1;
            }
        } else {
            return handshake_error(s);
        }
    }
    return L"i30 CE TLS handshake exceeded the step limit.\r\n";
}

enum I30AuthResult i30_ce_authenticate(const I30Link *link, void (*start_video)(void *),
                                      void (*video_presented)(void *))
{
    uint32_t attributes = GetFileAttributesW(I30_AA_AARE_MODE);
    int aare = attributes != 0xffffffffU && !(attributes & 0x10U);
    CE_HANDLE ca_file = open_credential(aare ? TLS_PATH L"i30-aare-ca.der" : TLS_PATH L"i30-ca.der",
                                         aare ? TLS_PATH L"i30-aare-ca.pem" : TLS_PATH L"i30-ca.pem");
    if (ca_file == (CE_HANDLE)-1) {
        if (missing_file(GetLastError())) {
            OutputDebugStringW(L"i30 CE TLS waiting for enrolled trust material.\r\n");
        } else {
            debug_file_error(FILE_UNREADABLE);
            OutputDebugStringW(L"i30 CE TLS trust CA missing, unreadable or invalid.\r\n");
        }
        return I30_AUTH_CONFIG;
    }
    Session *session = LocalAlloc(0x40, sizeof(*session)); /* Fixed, zero initialized. */
    if (!session) {
        CloseHandle(ca_file);
        OutputDebugStringW(L"i30 CE TLS session allocation failed.\r\n");
        return I30_AUTH_FAILED;
    }
    const CE_WCHAR *status = configure(session, ca_file, aare);
    enum I30AuthResult result = I30_AUTH_CONFIG;
    if (!status) {
        status = handshake(session, link);
        unsigned error = br_ssl_engine_last_error(&session->client.eng);
        result = I30_AUTH_FAILED;
        if (error == BR_ERR_RECV_FATAL_ALERT + 42U || error == BR_ERR_RECV_FATAL_ALERT + 46U ||
            error == BR_ERR_RECV_FATAL_ALERT + 48U)
            result = I30_AUTH_PHONE_REFUSED;
        if (!status) {
            result = I30_AUTH_ENDED;
            if (!discover(session, link, start_video, video_presented)) {
                status = L"i30 CE service discovery incomplete.\r\n";
                result = I30_AUTH_MEDIA_FAILED;
            }
        }
    }
    if (status)
        OutputDebugStringW(status);
    for (unsigned i = 0; i < sizeof(*session); ++i)
        ((volatile uint8_t *)session)[i] = 0;
    LocalFree(session);
    return result;
}
