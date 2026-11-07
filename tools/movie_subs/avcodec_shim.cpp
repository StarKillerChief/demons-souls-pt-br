// Movie subtitles without touching the game program.
//
// Soulbrandt opens FFmpeg's avcodec-62.dll at run time and resolves a small set of functions by name. This DLL takes
// that name, forwards everything to the real library (kept beside it as avcodec-62.orig.dll) and blends subtitle
// sprites into decoded pictures. If anything is missing, it only forwards: movies play as they always did.
//
// Pictures are copied before blending, because the decoder still uses its own buffers as reference frames.
//
// Files, in <dll folder>/movie_subs/:
//   <hash>.subs   one line per sprite: first_frame end_frame x y w h name.rgba
//   name.rgba     w*h*4 bytes, R G B A, made on the player's PC by make_movie_subs.py
// <hash> is the FNV-1a hash of the first packet sent to a decoder, in lowercase hex. It names the movie.
//
// Tools for the subtitle authors (off unless set):
//   BR_SUBS_LOG=<file>   writes each movie's hash and frame count
//   BR_SUBS_DUMP=<dir>   writes every 3rd frame's luma at quarter size, as <hash>_<frame>.raw
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

// FFmpeg lays these out the same way for a whole major version (see Soulbrandt's ffmpeg_runtime.h); this DLL is only
// ever installed over major 62. Only the fields used here are named.
struct FrameView {
    uint8_t* data[8];
    int linesize[8];
    uint8_t** extended_data;
    int width, height, nb_samples, format;
};
struct PacketView {
    void* buf;
    int64_t pts, dts;
    uint8_t* data;
    int size;
};
static const int kYuv420p = 0;

using Fn = void*;
static HMODULE g_real;
static std::mutex g_mu;
static Fn p_version, p_find, p_alloc, p_open, p_free, p_send, p_recv, p_flush, p_pkt_alloc, p_pkt_free, p_pinit, p_pparse,
    p_pclose;

static std::string dll_dir()
{
    HMODULE self = nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)&dll_dir, &self);
    char buf[MAX_PATH * 2];
    DWORD n = GetModuleFileNameA(self, buf, sizeof buf);
    std::string s(buf, n);
    return s.substr(0, s.find_last_of("\\/") + 1);
}

static void load_real()
{
    std::lock_guard<std::mutex> lk(g_mu);
    if (g_real) return;
    g_real = LoadLibraryA((dll_dir() + "avcodec-62.orig.dll").c_str());
    if (!g_real) return;
    p_version = (Fn)GetProcAddress(g_real, "avcodec_version");
    p_find = (Fn)GetProcAddress(g_real, "avcodec_find_decoder");
    p_alloc = (Fn)GetProcAddress(g_real, "avcodec_alloc_context3");
    p_open = (Fn)GetProcAddress(g_real, "avcodec_open2");
    p_free = (Fn)GetProcAddress(g_real, "avcodec_free_context");
    p_send = (Fn)GetProcAddress(g_real, "avcodec_send_packet");
    p_recv = (Fn)GetProcAddress(g_real, "avcodec_receive_frame");
    p_flush = (Fn)GetProcAddress(g_real, "avcodec_flush_buffers");
    p_pkt_alloc = (Fn)GetProcAddress(g_real, "av_packet_alloc");
    p_pkt_free = (Fn)GetProcAddress(g_real, "av_packet_free");
    p_pinit = (Fn)GetProcAddress(g_real, "av_parser_init");
    p_pparse = (Fn)GetProcAddress(g_real, "av_parser_parse2");
    p_pclose = (Fn)GetProcAddress(g_real, "av_parser_close");
}

struct Sprite {
    int first, end, x, y, w, h;
    std::vector<uint8_t> y_a;   // w*h pairs: luma, alpha
    std::vector<uint8_t> uv_a;  // (w/2)*(h/2) triples: u, v, alpha
};

struct Stream {
    void* ctx = nullptr;
    bool named = false;
    char hash[17] = {0};
    int frames = 0;
    std::vector<Sprite> sprites;
    std::vector<uint8_t> pic;  // the copy handed out while a sprite is showing
};
static std::vector<Stream*> g_streams;

static Stream* stream_of(void* ctx)
{
    std::lock_guard<std::mutex> lk(g_mu);
    for (Stream* s : g_streams)
        if (s->ctx == ctx) return s;
    Stream* s = new Stream();
    s->ctx = ctx;
    g_streams.push_back(s);
    return s;
}

static void log_line(const char* fmt, const char* hash, int n)
{
    const char* p = getenv("BR_SUBS_LOG");
    if (!p) return;
    if (FILE* f = fopen(p, "a")) {
        fprintf(f, fmt, hash, n);
        fclose(f);
    }
}

// RGBA to BT.709 limited range, the same matrix the game's movie code assumes.
static inline uint8_t clamp8(int v) { return (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : v); }
static void to_yuv(int r, int g, int b, uint8_t& y, uint8_t& u, uint8_t& v)
{
    y = clamp8(16 + (47 * r + 157 * g + 16 * b) / 256);
    u = clamp8(128 + (-26 * r - 87 * g + 112 * b) / 256);
    v = clamp8(128 + (112 * r - 102 * g - 10 * b) / 256);
}

static void load_sprites(Stream* s)
{
    std::string dir = dll_dir() + "movie_subs\\";
    FILE* f = fopen((dir + s->hash + ".subs").c_str(), "r");
    if (!f) return;
    Sprite sp;
    char name[260];
    while (fscanf(f, "%d %d %d %d %d %d %259s", &sp.first, &sp.end, &sp.x, &sp.y, &sp.w, &sp.h, name) == 7) {
        size_t n = (size_t)sp.w * sp.h * 4;
        std::vector<uint8_t> rgba(n);
        FILE* g = fopen((dir + name).c_str(), "rb");
        if (!g) continue;
        size_t got = fread(rgba.data(), 1, n, g);
        fclose(g);
        if (got != n) continue;
        sp.x &= ~1;
        sp.y &= ~1;
        sp.y_a.resize((size_t)sp.w * sp.h * 2);
        for (int i = 0; i < sp.w * sp.h; i++) {
            uint8_t y, u, v;
            to_yuv(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2], y, u, v);
            sp.y_a[i * 2] = y;
            sp.y_a[i * 2 + 1] = rgba[i * 4 + 3];
        }
        const int cw = sp.w / 2, ch = sp.h / 2;
        sp.uv_a.resize((size_t)cw * ch * 3);
        for (int cy = 0; cy < ch; cy++)
            for (int cx = 0; cx < cw; cx++) {
                int r = 0, g2 = 0, b = 0, a = 0;
                for (int k = 0; k < 4; k++) {
                    const uint8_t* p = &rgba[(((size_t)cy * 2 + (k >> 1)) * sp.w + cx * 2 + (k & 1)) * 4];
                    r += p[0] * p[3];
                    g2 += p[1] * p[3];
                    b += p[2] * p[3];
                    a += p[3];
                }
                uint8_t y, u = 128, v = 128;
                if (a) to_yuv(r / a, g2 / a, b / a, y, u, v);
                uint8_t* o = &sp.uv_a[((size_t)cy * cw + cx) * 3];
                o[0] = u;
                o[1] = v;
                o[2] = (uint8_t)(a / 4);
            }
        s->sprites.push_back(std::move(sp));
        sp = Sprite();
    }
    fclose(f);
    log_line("subs %s: %d sprites\n", s->hash, (int)s->sprites.size());
}

static void dump_luma(const Stream* s, const FrameView* f, int no)
{
    static const char* dir = getenv("BR_SUBS_DUMP");
    if (!dir || no % 3) return;
    char name[64];
    snprintf(name, sizeof name, "\\%s_%06d.raw", s->hash, no);
    if (FILE* g = fopen((std::string(dir) + name).c_str(), "wb")) {
        for (int y = 0; y < f->height; y += 4)
            for (int x = 0; x < f->width; x += 4) fputc(f->data[0][(size_t)y * f->linesize[0] + x], g);
        fclose(g);
    }
}

static void blend(Stream* s, FrameView* f, int no)
{
    bool any = false;
    for (const Sprite& sp : s->sprites)
        if (no >= sp.first && no < sp.end) any = true;
    if (!any || f->format != kYuv420p) return;

    // Copy the three planes and point the frame at the copy. The caller reads data[] and linesize[] and then unrefs,
    // which releases the decoder's buffers through buf[], so swapping the pointers is safe.
    const int w = f->width, h = f->height, cw = w / 2, ch = h / 2;
    s->pic.resize((size_t)w * h + (size_t)cw * ch * 2);
    uint8_t* yp = s->pic.data();
    uint8_t* up = yp + (size_t)w * h;
    uint8_t* vp = up + (size_t)cw * ch;
    for (int y = 0; y < h; y++) memcpy(yp + (size_t)y * w, f->data[0] + (size_t)y * f->linesize[0], w);
    for (int y = 0; y < ch; y++) {
        memcpy(up + (size_t)y * cw, f->data[1] + (size_t)y * f->linesize[1], cw);
        memcpy(vp + (size_t)y * cw, f->data[2] + (size_t)y * f->linesize[2], cw);
    }
    for (const Sprite& sp : s->sprites) {
        if (no < sp.first || no >= sp.end) continue;
        for (int y = 0; y < sp.h && y + sp.y < h; y++)
            for (int x = 0; x < sp.w && x + sp.x < w; x++) {
                const uint8_t* q = &sp.y_a[((size_t)y * sp.w + x) * 2];
                uint8_t* o = yp + (size_t)(y + sp.y) * w + x + sp.x;
                *o = (uint8_t)((q[0] * q[1] + *o * (255 - q[1])) / 255);
            }
        const int scw = sp.w / 2, sch = sp.h / 2, ox = sp.x / 2, oy = sp.y / 2;
        for (int y = 0; y < sch && y + oy < ch; y++)
            for (int x = 0; x < scw && x + ox < cw; x++) {
                const uint8_t* q = &sp.uv_a[((size_t)y * scw + x) * 3];
                const size_t at = (size_t)(y + oy) * cw + x + ox;
                up[at] = (uint8_t)((q[0] * q[2] + up[at] * (255 - q[2])) / 255);
                vp[at] = (uint8_t)((q[1] * q[2] + vp[at] * (255 - q[2])) / 255);
            }
    }
    f->data[0] = yp;
    f->data[1] = up;
    f->data[2] = vp;
    f->linesize[0] = w;
    f->linesize[1] = cw;
    f->linesize[2] = cw;
}

#define EXPORT extern "C" __declspec(dllexport)
#define REAL(ptr, type) (load_real(), reinterpret_cast<type>(ptr))

EXPORT unsigned avcodec_version(void)
{
    auto fn = REAL(p_version, unsigned (*)());
    return fn ? fn() : 0;  // 0 makes the game reject this library and use its other decoder
}
EXPORT const void* avcodec_find_decoder(int id)
{
    auto fn = REAL(p_find, const void* (*)(int));
    return fn ? fn(id) : nullptr;
}
EXPORT void* avcodec_alloc_context3(const void* c)
{
    auto fn = REAL(p_alloc, void* (*)(const void*));
    return fn ? fn(c) : nullptr;
}
EXPORT int avcodec_open2(void* ctx, const void* c, void** opts)
{
    return REAL(p_open, int (*)(void*, const void*, void**))(ctx, c, opts);
}
EXPORT void avcodec_free_context(void** pctx)
{
    if (pctx && *pctx) {
        Stream* s = stream_of(*pctx);
        if (s->named) log_line("movie %s: %d frames\n", s->hash, s->frames);
        std::lock_guard<std::mutex> lk(g_mu);
        for (size_t i = 0; i < g_streams.size(); i++)
            if (g_streams[i] == s) {
                g_streams.erase(g_streams.begin() + i);
                delete s;
                break;
            }
    }
    REAL(p_free, void (*)(void**))(pctx);
}
EXPORT int avcodec_send_packet(void* ctx, const void* pkt)
{
    if (pkt) {
        Stream* s = stream_of(ctx);
        const PacketView* p = static_cast<const PacketView*>(pkt);
        if (!s->named && p->data && p->size > 0) {
            uint64_t h = 0xcbf29ce484222325ull;
            for (int i = 0; i < p->size; i++) h = (h ^ p->data[i]) * 0x100000001b3ull;
            snprintf(s->hash, sizeof s->hash, "%016llx", (unsigned long long)h);
            s->named = true;
            log_line("open %s (%d)\n", s->hash, p->size);
            load_sprites(s);
        }
    }
    return REAL(p_send, int (*)(void*, const void*))(ctx, pkt);
}
EXPORT int avcodec_receive_frame(void* ctx, void* frame)
{
    const int r = REAL(p_recv, int (*)(void*, void*))(ctx, frame);
    if (r >= 0) {
        Stream* s = stream_of(ctx);
        FrameView* f = static_cast<FrameView*>(frame);
        const int no = s->frames++;
        if (s->named) {
            dump_luma(s, f, no);
            if (!s->sprites.empty()) blend(s, f, no);
        }
    }
    return r;
}
EXPORT void avcodec_flush_buffers(void* ctx)
{
    REAL(p_flush, void (*)(void*))(ctx);
}
EXPORT void* av_packet_alloc(void) { return REAL(p_pkt_alloc, void* (*)())(); }
EXPORT void av_packet_free(void** p) { REAL(p_pkt_free, void (*)(void**))(p); }
EXPORT void* av_parser_init(int id) { return REAL(p_pinit, void* (*)(int))(id); }
EXPORT int av_parser_parse2(void* s, void* ctx, uint8_t** out, int* out_size, const uint8_t* buf, int buf_size,
                            int64_t pts, int64_t dts, int64_t pos)
{
    return REAL(p_pparse, int (*)(void*, void*, uint8_t**, int*, const uint8_t*, int, int64_t, int64_t, int64_t))(
        s, ctx, out, out_size, buf, buf_size, pts, dts, pos);
}
EXPORT void av_parser_close(void* s) { REAL(p_pclose, void (*)(void*))(s); }
