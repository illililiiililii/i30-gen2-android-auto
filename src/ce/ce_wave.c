#include "ce_wave.h"

static void pcm_format(WAVEFORMATEX *fmt, DWORD rate, WORD channels)
{
    fmt->wFormatTag = WAVE_FORMAT_PCM;
    fmt->nChannels = channels;
    fmt->nSamplesPerSec = rate;
    fmt->nBlockAlign = channels * 2;
    fmt->nAvgBytesPerSec = rate * fmt->nBlockAlign;
    fmt->wBitsPerSample = 16;
    fmt->cbSize = 0;
}

MMRESULT i30_playback_query(UINT device)
{
    WAVEFORMATEX fmt;
    pcm_format(&fmt, 48000, 2);
    return waveOutOpen(NULL, device, &fmt, 0, 0, WAVE_FORMAT_QUERY);
}

MMRESULT i30_capture_query(UINT device)
{
    WAVEFORMATEX fmt;
    pcm_format(&fmt, 16000, 1);
    return waveInOpen(NULL, device, &fmt, 0, 0, WAVE_FORMAT_QUERY);
}

MMRESULT i30_playback_open(I30Playback *out, UINT device, BOOL stock_granted)
{
    WAVEFORMATEX fmt;
    MMRESULT result, cleanup;
    UINT i;

    if (!stock_granted || out->handle)
        return MMSYSERR_ALLOCATED;
    pcm_format(&fmt, 48000, 2);
    result = waveOutOpen(&out->handle, device, &fmt, 0, 0, CALLBACK_NULL);
    if (result != MMSYSERR_NOERROR)
        return result;
    out->cursor = 0;
    for (i = 0; i < I30_WAVE_SLOTS; ++i) {
        WAVEHDR *header = &out->slots[i];
        ZeroMemory(header, sizeof(*header));
        header->lpData = (LPSTR)out->data[i];
        header->dwBufferLength = I30_PLAYBACK_BYTES;
        result = waveOutPrepareHeader(out->handle, header, sizeof(*header));
        if (result != MMSYSERR_NOERROR) {
            cleanup = i30_playback_close(out);
            return cleanup == MMSYSERR_NOERROR ? result : cleanup;
        }
    }
    return MMSYSERR_NOERROR;
}

MMRESULT i30_capture_open(I30Capture *in, UINT device, BOOL stock_granted)
{
    WAVEFORMATEX fmt;
    MMRESULT result, cleanup;
    UINT i;

    if (!stock_granted || in->handle)
        return MMSYSERR_ALLOCATED;
    pcm_format(&fmt, 16000, 1);
    result = waveInOpen(&in->handle, device, &fmt, 0, 0, CALLBACK_NULL);
    if (result != MMSYSERR_NOERROR)
        return result;
    in->cursor = 0;
    for (i = 0; i < I30_WAVE_SLOTS; ++i) {
        WAVEHDR *header = &in->slots[i];
        ZeroMemory(header, sizeof(*header));
        header->lpData = (LPSTR)in->data[i];
        header->dwBufferLength = I30_CAPTURE_BYTES;
        result = waveInPrepareHeader(in->handle, header, sizeof(*header));
        if (result == MMSYSERR_NOERROR)
            result = waveInAddBuffer(in->handle, header, sizeof(*header));
        if (result != MMSYSERR_NOERROR)
            break;
    }
    if (result == MMSYSERR_NOERROR)
        result = waveInStart(in->handle);
    if (result != MMSYSERR_NOERROR) {
        cleanup = i30_capture_close(in);
        if (cleanup != MMSYSERR_NOERROR)
            return cleanup;
    }
    return result;
}

MMRESULT i30_playback_write(I30Playback *out, const BYTE *pcm, DWORD size)
{
    MMRESULT result;
    WAVEHDR *header = &out->slots[out->cursor];
    if (!out->handle)
        return MMSYSERR_INVALHANDLE;
    if (!pcm || size != I30_PLAYBACK_BYTES)
        return MMSYSERR_INVALPARAM;
    if (header->dwFlags & WHDR_INQUEUE)
        return WAVERR_STILLPLAYING;
    CopyMemory(header->lpData, pcm, size);
    result = waveOutWrite(out->handle, header, sizeof(*header));
    if (result == MMSYSERR_NOERROR)
        out->cursor = (out->cursor + 1) % I30_WAVE_SLOTS;
    return result;
}

MMRESULT i30_capture_read(I30Capture *in, BYTE *pcm, DWORD capacity, DWORD *size)
{
    DWORD recorded;
    MMRESULT result;
    WAVEHDR *header = &in->slots[in->cursor];
    if (!in->handle)
        return MMSYSERR_INVALHANDLE;
    if (!size || !pcm || capacity < I30_CAPTURE_BYTES)
        return MMSYSERR_INVALPARAM;
    *size = 0;
    if (!(header->dwFlags & WHDR_DONE))
        return MMSYSERR_NOERROR;
    recorded = header->dwBytesRecorded;
    if (recorded > I30_CAPTURE_BYTES || (recorded & 1))
        return MMSYSERR_ERROR;
    CopyMemory(pcm, header->lpData, recorded);
    result = waveInAddBuffer(in->handle, header, sizeof(*header));
    if (result == MMSYSERR_NOERROR) {
        *size = recorded;
        in->cursor = (in->cursor + 1) % I30_WAVE_SLOTS;
    }
    return result;
}

MMRESULT i30_playback_close(I30Playback *out)
{
    MMRESULT result;
    UINT i;
    if (!out->handle)
        return MMSYSERR_NOERROR;
    result = waveOutReset(out->handle);
    for (i = 0; result == MMSYSERR_NOERROR && i < I30_WAVE_SLOTS; ++i) {
        WAVEHDR *header = &out->slots[i];
        if (header->dwFlags & WHDR_PREPARED)
            result = waveOutUnprepareHeader(out->handle, header, sizeof(*header));
    }
    if (result == MMSYSERR_NOERROR)
        result = waveOutClose(out->handle);
    if (result == MMSYSERR_NOERROR)
        out->handle = NULL;
    return result;
}

MMRESULT i30_capture_close(I30Capture *in)
{
    MMRESULT result;
    UINT i;
    if (!in->handle)
        return MMSYSERR_NOERROR;
    result = waveInReset(in->handle);
    for (i = 0; result == MMSYSERR_NOERROR && i < I30_WAVE_SLOTS; ++i) {
        WAVEHDR *header = &in->slots[i];
        if (header->dwFlags & WHDR_PREPARED)
            result = waveInUnprepareHeader(in->handle, header, sizeof(*header));
    }
    if (result == MMSYSERR_NOERROR)
        result = waveInClose(in->handle);
    if (result == MMSYSERR_NOERROR)
        in->handle = NULL;
    return result;
}
