// PT-BR.exe - the launcher of the Demon's Souls PT-BR translation.
// It draws the window; launcher_backend.py (run with the pack's own Python) does all the file work.
// Nothing from the game is inside this program: the logo and paintings are exported from the player's own copy by
// the back end at run time (cache\art), and only a crop table lives here.
//
// Test hook (renders one screen to a PNG and exits, no back end, no game files touched):
//   PT-BR.exe --snapshot out.png --screen home|targets|rpcs3|rpcs3bad|installing|installed|installed-rpcs3|
//             confirm|about|uninstalled|error|notfound|fontchange [--art DIR] [--hero N]
#define _WIN32_WINNT 0x0A00               // Windows 10 or later (per-monitor DPI v2)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>
#include <shobjidl.h>
#include <dwmapi.h>
#include <d2d1.h>
#include <dwrite_3.h>
#include <wincodec.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <functional>
#include <string>
#include <thread>
#include <vector>

#include "json.h"

template <class T> struct Com {
    T *p = nullptr;
    Com() = default;
    ~Com() { if (p) p->Release(); }
    Com(const Com &) = delete;
    Com &operator=(const Com &) = delete;
    T **operator&() { if (p) { p->Release(); p = nullptr; } return &p; }
    T *operator->() const { return p; }
    operator T *() const { return p; }
    void reset() { if (p) { p->Release(); p = nullptr; } }
};

// ---------------------------------------------------------------------------------------------------------- text
static std::wstring W(const std::string &u8) {
    if (u8.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, u8.data(), (int)u8.size(), nullptr, 0);
    std::wstring w(n, 0);
    MultiByteToWideChar(CP_UTF8, 0, u8.data(), (int)u8.size(), &w[0], n);
    return w;
}
static std::string U8(const std::wstring &w) {
    if (w.empty()) return "";
    int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n, 0);
    WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

// ---------------------------------------------------------------------------------------------------------- paths
static std::wstring g_dir;          // folder of PT-BR.exe
static std::wstring path(const std::wstring &rel) { return g_dir + L"\\" + rel; }
static bool exists(const std::wstring &p) { return GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES; }

// ---------------------------------------------------------------------------------------------------------- design
static const D2D1_COLOR_F BG = D2D1::ColorF(0x060504), INK = D2D1::ColorF(0xe4dcc9), INK2 = D2D1::ColorF(0xa39b88),
                          INK3 = D2D1::ColorF(0x7d7666), GOLD = D2D1::ColorF(0xbfa066), GOLDHI = D2D1::ColorF(0xecd9a6),
                          OK = D2D1::ColorF(0x8aa56b), ERR = D2D1::ColorF(0xc4624a), LINE = D2D1::ColorF(0x2e2820),
                          PANEL = D2D1::ColorF(0x0c0a08, 0.72f);
static const float WIN_W = 960, WIN_H = 560, HERO_H = 250, SHEET_X = 150, SHEET_W = 660;
static const wchar_t *GITHUB = L"https://github.com/StarKillerChief/demons-souls-pt-br";

struct Crop { const wchar_t *key; float y; };
// painting (cleaned export, 1024x720) scaled to 960 px wide; y = vertical offset inside the 250 px band
static const Crop HEROES[] = {{L"13", -92}, {L"10", -17}, {L"05", -58}, {L"14", 0},
                              {L"16", -62}, {L"15", -65}, {L"08", 0},   {L"03", -136}};
static const int NHERO = sizeof(HEROES) / sizeof(HEROES[0]);

// ---------------------------------------------------------------------------------------------------------- state
enum Screen { S_LOADING, S_HOME, S_TARGETS, S_RPCS3, S_INSTALLING, S_INSTALLED, S_UNINSTALLING, S_UNINSTALLED,
              S_ERROR, S_NOTFOUND, S_FONTCHANGE };
enum Modal { M_NONE, M_CONFIRM, M_ABOUT, M_SAMEFONT };

struct App {
    HWND hwnd = nullptr;
    Screen screen = S_LOADING;
    Modal modal = M_NONE;
    // what the back end found
    bool sb_found = false, sb_prepared = false, sb_running = false, sb_installed = false, sb_subs = false;
    std::wstring sb_program, sb_game, sb_fonts;
    std::wstring rp_game;                     // chosen / detected RPCS3 game folder
    bool rp_installed = false;
    std::wstring rp_fonts;
    int rp_check = 0;                         // 0 none, 1 ok, -1 bad, 2 checking
    std::wstring rp_msg;
    // choices
    bool target_rpcs3 = false, target_pick_rpcs3 = false;
    std::wstring font = L"original";       // original | novas (hd: only a v0.1.1 install, kept on Reinstalar)
    // install progress
    bool busy = false, uninstalling = false;
    int pct = 0, loading_n = 0;
    std::string step;
    ULONGLONG t_start = 0;
    std::wstring err_title, err_msg, err_code;
    bool done_fresh = false;
    // art
    bool art_ready = false;
    ULONGLONG art_t = 0;
    int hero = 0, hero_next = 1;
    ULONGLONG hero_t = 0, hero_fade_t = 0;
    bool reduced_motion = false;
    // ui
    int hover = 0, pressed = 0, focus = 0;
    bool kb_focus = false;
} app;

// ---------------------------------------------------------------------------------------------------------- back end
#define WM_APP_LINE (WM_APP + 1)
#define WM_APP_EXIT (WM_APP + 2)

struct Job { int kind; };                     // posted with lines: wParam = kind, lParam = new std::string*
enum JobKind { J_STATE = 1, J_ART, J_INSTALL, J_UNINSTALL, J_VALIDATE };

static void run_backend(int kind, const std::wstring &args) {
    std::wstring py = path(L"python\\python.exe"), be = path(L"pack\\tools\\launcher_backend.py");
    std::wstring cmd = L"\"" + py + L"\" -I -u -X utf8 \"" + be + L"\" " + args;
    HWND hwnd = app.hwnd;
    std::thread([kind, cmd, hwnd]() {
        SECURITY_ATTRIBUTES sa{sizeof(sa), nullptr, TRUE};
        HANDLE rd = nullptr, wr = nullptr;
        CreatePipe(&rd, &wr, &sa, 0);
        SetHandleInformation(rd, HANDLE_FLAG_INHERIT, 0);
        CreateDirectoryW(path(L"cache").c_str(), nullptr);
        HANDLE log = CreateFileW(path(L"cache\\registro.txt").c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, &sa,
                                 OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        HANDLE nul = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, nullptr);
        STARTUPINFOW si{};
        si.cb = sizeof(si);
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdOutput = wr;
        si.hStdError = log != INVALID_HANDLE_VALUE ? log : wr;
        si.hStdInput = nul;
        PROCESS_INFORMATION pi{};
        std::wstring c = cmd;
        BOOL ok = CreateProcessW(nullptr, &c[0], nullptr, nullptr, TRUE, CREATE_NO_WINDOW, nullptr,
                                 g_dir.c_str(), &si, &pi);
        CloseHandle(wr);
        if (nul != INVALID_HANDLE_VALUE) CloseHandle(nul);
        if (log != INVALID_HANDLE_VALUE) CloseHandle(log);
        DWORD code = 99;
        if (ok) {
            std::string buf;
            char chunk[4096];
            DWORD n = 0;
            while (ReadFile(rd, chunk, sizeof(chunk), &n, nullptr) && n) {
                buf.append(chunk, n);
                size_t p;
                while ((p = buf.find('\n')) != std::string::npos) {
                    std::string line = buf.substr(0, p);
                    if (!line.empty() && line.back() == '\r') line.pop_back();
                    buf.erase(0, p + 1);
                    PostMessageW(hwnd, WM_APP_LINE, kind, (LPARAM) new std::string(line));
                }
            }
            if (!buf.empty()) PostMessageW(hwnd, WM_APP_LINE, kind, (LPARAM) new std::string(buf));
            WaitForSingleObject(pi.hProcess, INFINITE);
            GetExitCodeProcess(pi.hProcess, &code);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
        }
        CloseHandle(rd);
        PostMessageW(hwnd, WM_APP_EXIT, kind, (LPARAM)code);
    }).detach();
}

static std::wstring q(const std::wstring &s) { return L"\"" + s + L"\""; }

static void save_prefs() {
    std::wstring ini = path(L"cache\\launcher.ini");
    CreateDirectoryW(path(L"cache").c_str(), nullptr);
    WritePrivateProfileStringW(L"launcher", L"target", app.target_rpcs3 ? L"rpcs3" : L"soulbrandt", ini.c_str());
    WritePrivateProfileStringW(L"launcher", L"rpcs3", app.rp_game.c_str(), ini.c_str());
}
static void load_prefs() {
    std::wstring ini = path(L"cache\\launcher.ini");
    wchar_t buf[1024];
    GetPrivateProfileStringW(L"launcher", L"target", L"", buf, 1024, ini.c_str());
    app.target_rpcs3 = std::wstring(buf) == L"rpcs3";
    GetPrivateProfileStringW(L"launcher", L"rpcs3", L"", buf, 1024, ini.c_str());
    app.rp_game = buf;
}

static void start_art() {
    if (exists(path(L"cache\\art\\logo.png"))) { app.art_ready = true; app.art_t = GetTickCount64(); return; }
    std::wstring args = L"art --out " + q(path(L"cache\\art"));
    if (app.target_rpcs3 && !app.rp_game.empty()) args += L" --target rpcs3 --game " + q(app.rp_game);
    else if (!app.sb_found || !app.sb_prepared) {
        if (app.rp_game.empty()) return;
        args += L" --target rpcs3 --game " + q(app.rp_game);
    }
    run_backend(J_ART, args);
}

static void start_install(bool uninstall) {
    app.busy = true;
    app.uninstalling = uninstall;
    app.pct = 2;
    app.loading_n = 0;
    app.step = "prepare";
    app.t_start = GetTickCount64();
    app.screen = uninstall ? S_UNINSTALLING : S_INSTALLING;
    app.modal = M_NONE;
    app.focus = 0;
    std::wstring args = uninstall ? L"uninstall" : L"install";
    args += app.target_rpcs3 ? L" --target rpcs3 --game " + q(app.rp_game) : L" --target soulbrandt";
    if (!uninstall) args += L" --fonts " + app.font;
    run_backend(uninstall ? J_UNINSTALL : J_INSTALL, args);
}

// ---------------------------------------------------------------------------------------------------------- D2D
static Com<ID2D1Factory> d2d;
static Com<IDWriteFactory> dw;
static Com<IDWriteFontCollection> fonts;
static Com<IWICImagingFactory> wic;
static const wchar_t *FAMILY = L"EB Garamond";

struct Res {                                  // device resources for one render target
    ID2D1RenderTarget *rt = nullptr;
    Com<ID2D1SolidColorBrush> br;
    std::vector<ID2D1Bitmap *> heroes;        // baked 960x250 bands
    ID2D1Bitmap *logo = nullptr;
    bool art_loaded = false;
    void drop() {
        for (auto b : heroes) if (b) b->Release();
        heroes.clear();
        if (logo) { logo->Release(); logo = nullptr; }
        art_loaded = false;
        br.reset();
        if (rt) { rt->Release(); rt = nullptr; }
    }
} R;

static void init_factories() {
    D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &d2d);
    DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory), (IUnknown **)&dw);
    CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&wic));
    // EB Garamond (SIL OFL) from the pack, as a private collection; Georgia if anything fails
    Com<IDWriteFactory5> f5;
    if (SUCCEEDED(dw->QueryInterface(__uuidof(IDWriteFactory5), (void **)&f5))) {
        Com<IDWriteFontSetBuilder1> sb;
        Com<IDWriteFontFile> file;
        std::wstring ttf = path(L"pack\\tools\\fonts\\EBGaramond.ttf");
        if (SUCCEEDED(f5->CreateFontSetBuilder(&sb)) && SUCCEEDED(f5->CreateFontFileReference(ttf.c_str(), nullptr, &file)) &&
            SUCCEEDED(sb->AddFontFile(file))) {
            Com<IDWriteFontSet> set;
            Com<IDWriteFontCollection1> col;
            if (SUCCEEDED(sb->CreateFontSet(&set)) && SUCCEEDED(f5->CreateFontCollectionFromFontSet(set, &col)))
                col->QueryInterface(__uuidof(IDWriteFontCollection), (void **)&fonts);
        }
    }
    if (!fonts) FAMILY = L"Georgia";
}

static IDWriteTextFormat *fmt(float size, DWRITE_FONT_WEIGHT w = DWRITE_FONT_WEIGHT_NORMAL, bool italic = false) {
    IDWriteTextFormat *f = nullptr;
    dw->CreateTextFormat(FAMILY, fonts, w, italic ? DWRITE_FONT_STYLE_ITALIC : DWRITE_FONT_STYLE_NORMAL,
                         DWRITE_FONT_STRETCH_NORMAL, size, L"pt-BR", &f);
    return f;
}

enum Align { LEFT, CENTER, RIGHT };
static float text(const std::wstring &s, float x, float y, float w, float size, D2D1_COLOR_F c,
                  DWRITE_FONT_WEIGHT wt = DWRITE_FONT_WEIGHT_NORMAL, Align al = LEFT, float h = 400, bool italic = false,
                  float spacing = 0) {
    IDWriteTextFormat *f = fmt(size, wt, italic);
    if (!f) return 0;
    f->SetTextAlignment(al == LEFT ? DWRITE_TEXT_ALIGNMENT_LEADING : al == CENTER ? DWRITE_TEXT_ALIGNMENT_CENTER
                                                                                  : DWRITE_TEXT_ALIGNMENT_TRAILING);
    f->SetWordWrapping(DWRITE_WORD_WRAPPING_WRAP);
    IDWriteTextLayout *l = nullptr;
    dw->CreateTextLayout(s.c_str(), (UINT32)s.size(), f, w, h, &l);
    float height = 0;
    if (l) {
        if (spacing) {
            Com<IDWriteTextLayout1> l1;
            if (SUCCEEDED(l->QueryInterface(__uuidof(IDWriteTextLayout1), (void **)&l1)))
                l1->SetCharacterSpacing(0, spacing, 0, DWRITE_TEXT_RANGE{0, (UINT32)s.size()});
        }
        DWRITE_TEXT_METRICS m{};
        l->GetMetrics(&m);
        height = m.height;
        R.br->SetColor(c);
        R.rt->DrawTextLayout(D2D1::Point2F(x, y), l, R.br, D2D1_DRAW_TEXT_OPTIONS_NONE);
        l->Release();
    }
    f->Release();
    return height;
}
static float text_width(const std::wstring &s, float size, DWRITE_FONT_WEIGHT wt = DWRITE_FONT_WEIGHT_NORMAL) {
    IDWriteTextFormat *f = fmt(size, wt);
    IDWriteTextLayout *l = nullptr;
    float w = 0;
    if (f && SUCCEEDED(dw->CreateTextLayout(s.c_str(), (UINT32)s.size(), f, 2000, 200, &l))) {
        DWRITE_TEXT_METRICS m{};
        l->GetMetrics(&m);
        w = m.widthIncludingTrailingWhitespace;
        l->Release();
    }
    if (f) f->Release();
    return w;
}

static void fill(D2D1_RECT_F r, D2D1_COLOR_F c, float rad = 0) {
    R.br->SetColor(c);
    if (rad) R.rt->FillRoundedRectangle(D2D1::RoundedRect(r, rad, rad), R.br);
    else R.rt->FillRectangle(r, R.br);
}
static void stroke(D2D1_RECT_F r, D2D1_COLOR_F c, float w = 1, float rad = 0) {
    R.br->SetColor(c);
    if (rad) R.rt->DrawRoundedRectangle(D2D1::RoundedRect(r, rad, rad), R.br, w);
    else R.rt->DrawRectangle(r, R.br, w);
}
static void line(float x0, float y0, float x1, float y1, D2D1_COLOR_F c, float w = 1.6f) {
    R.br->SetColor(c);
    R.rt->DrawLine(D2D1::Point2F(x0, y0), D2D1::Point2F(x1, y1), R.br, w);
}
static void vgrad(D2D1_RECT_F r, D2D1_COLOR_F a, D2D1_COLOR_F b, float rad = 0) {
    D2D1_GRADIENT_STOP st[2] = {{0, a}, {1, b}};
    Com<ID2D1GradientStopCollection> sc;
    R.rt->CreateGradientStopCollection(st, 2, &sc);
    Com<ID2D1LinearGradientBrush> lg;
    R.rt->CreateLinearGradientBrush(D2D1::LinearGradientBrushProperties(D2D1::Point2F(0, r.top), D2D1::Point2F(0, r.bottom)),
                                    sc, &lg);
    if (rad) R.rt->FillRoundedRectangle(D2D1::RoundedRect(r, rad, rad), lg);
    else R.rt->FillRectangle(r, lg);
}
static D2D1_COLOR_F alpha(D2D1_COLOR_F c, float a) { c.a *= a; return c; }

// ---------------------------------------------------------------------------------------------------------- art
static bool load_pixels(const std::wstring &file, std::vector<uint8_t> &px, UINT &w, UINT &h) {
    Com<IWICBitmapDecoder> dec;
    if (FAILED(wic->CreateDecoderFromFilename(file.c_str(), nullptr, GENERIC_READ, WICDecodeMetadataCacheOnDemand, &dec)))
        return false;
    Com<IWICBitmapFrameDecode> fr;
    Com<IWICFormatConverter> cv;
    if (FAILED(dec->GetFrame(0, &fr)) || FAILED(wic->CreateFormatConverter(&cv)) ||
        FAILED(cv->Initialize(fr, GUID_WICPixelFormat32bppBGRA, WICBitmapDitherTypeNone, nullptr, 0, WICBitmapPaletteTypeCustom)))
        return false;
    cv->GetSize(&w, &h);
    px.resize((size_t)w * h * 4);
    return SUCCEEDED(cv->CopyPixels(nullptr, w * 4, (UINT)px.size(), px.data()));
}

static float smooth(float t) { t = std::min(1.f, std::max(0.f, t)); return t * t * (3 - 2 * t); }

// One hero band (960x250): the painting at 960 px wide, offset y, dimmed (62%) and desaturated (70%), fading to black
// on the left and at the bottom, like the prototype.
static ID2D1Bitmap *bake_hero(const std::wstring &file, float yoff) {
    std::vector<uint8_t> src;
    UINT w, h;
    if (!load_pixels(file, src, w, h) || w < 2 || h < 2) return nullptr;
    const int BW = 960, BH = (int)HERO_H;
    std::vector<uint8_t> out((size_t)BW * BH * 4);
    float sc = (float)w / BW;
    for (int y = 0; y < BH; y++) {
        float sy = (y - yoff) * sc;
        int iy = std::min((int)h - 1, std::max(0, (int)sy));
        float fade_b = 1 - smooth((y - BH * 0.55f) / (BH * 0.45f));
        float fade_t = 0.42f + 0.58f * smooth((y - 6.f) / 70.f);     // darker under the title bar
        for (int x = 0; x < BW; x++) {
            int ix = std::min((int)w - 1, (int)(x * sc));
            const uint8_t *p = &src[((size_t)iy * w + ix) * 4];
            float b = p[0], g = p[1], r = p[2];
            float lum = 0.299f * r + 0.587f * g + 0.114f * b;
            float sat = 0.70f;
            r = lum + (r - lum) * sat; g = lum + (g - lum) * sat; b = lum + (b - lum) * sat;
            float fade_l = smooth((x - 380.f) / 470.f);
            float k = 0.58f * fade_l * fade_b * fade_t;
            uint8_t *o = &out[((size_t)y * BW + x) * 4];
            o[0] = (uint8_t)std::min(255.f, b * k);
            o[1] = (uint8_t)std::min(255.f, g * k);
            o[2] = (uint8_t)std::min(255.f, r * k);
            o[3] = 255;
        }
    }
    ID2D1Bitmap *bm = nullptr;
    R.rt->CreateBitmap(D2D1::SizeU(BW, BH), out.data(), BW * 4,
                       D2D1::BitmapProperties(D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED)), &bm);
    return bm;
}

// The logo: grey value as coverage of white (premultiplied).
static ID2D1Bitmap *bake_logo(const std::wstring &file) {
    std::vector<uint8_t> px;
    UINT w, h;
    if (!load_pixels(file, px, w, h)) return nullptr;
    for (size_t i = 0; i < px.size(); i += 4) {
        uint8_t v = px[i + 1];
        px[i] = px[i + 1] = px[i + 2] = v;
        px[i + 3] = v;
    }
    ID2D1Bitmap *bm = nullptr;
    R.rt->CreateBitmap(D2D1::SizeU(w, h), px.data(), w * 4,
                       D2D1::BitmapProperties(D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED)), &bm);
    return bm;
}

static std::wstring g_artdir;                 // where the art PNGs are (cache\art, or --art for snapshots)

static void ensure_art() {
    if (R.art_loaded || !app.art_ready) return;
    R.art_loaded = true;
    R.logo = bake_logo(g_artdir + L"\\logo.png");
    for (int i = 0; i < NHERO; i++) {
        ID2D1Bitmap *b = bake_hero(g_artdir + L"\\" + HEROES[i].key + L".png", HEROES[i].y);
        if (b) R.heroes.push_back(b);
    }
    if (R.heroes.empty() && !R.logo) app.art_ready = false;
}

// ---------------------------------------------------------------------------------------------------------- widgets
struct Item { int id; D2D1_RECT_F r; bool enabled; };
static std::vector<Item> items;
static bool inside(D2D1_RECT_F r, float x, float y) { return x >= r.left && x < r.right && y >= r.top && y < r.bottom; }

enum Ids {
    ID_MIN = 1, ID_CLOSE, ID_CHANGE, ID_FONT_ORIG, ID_FONT_NEW, ID_INSTALL, ID_GITHUB, ID_ABOUT,
    ID_T_SB, ID_T_RP, ID_T_CONTINUE, ID_BACK, ID_BROWSE, ID_RP_CONTINUE,
    ID_OPEN, ID_REINSTALL, ID_CHANGEFONT, ID_UNINSTALL, ID_M_CANCEL, ID_M_OK, ID_M_CLOSE,
    ID_RETRY, ID_LOG, ID_INSTALL_AGAIN, ID_EXIT, ID_APPLY, ID_CHOOSE_RP, ID_M_REINSTALL
};

static bool focused(int id) { return app.kb_focus && app.focus == id; }
static void add(int id, D2D1_RECT_F r, bool en = true) { items.push_back({id, r, en}); }

enum Icon { I_NONE, I_PLAY, I_X, I_REFRESH, I_AA, I_TRASH, I_FOLDER };

static void icon(Icon ic, float cx, float cy, D2D1_COLOR_F c) {
    R.br->SetColor(c);
    switch (ic) {
    case I_PLAY: {
        Com<ID2D1PathGeometry> g;
        d2d->CreatePathGeometry(&g);
        Com<ID2D1GeometrySink> s;
        g->Open(&s);
        s->BeginFigure(D2D1::Point2F(cx - 5, cy - 7), D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddLine(D2D1::Point2F(cx + 7, cy));
        s->AddLine(D2D1::Point2F(cx - 5, cy + 7));
        s->EndFigure(D2D1_FIGURE_END_CLOSED);
        s->Close();
        R.rt->DrawGeometry(g, R.br, 1.6f);
        break;
    }
    case I_X:
        line(cx - 6, cy - 6, cx + 6, cy + 6, c); line(cx + 6, cy - 6, cx - 6, cy + 6, c);
        break;
    case I_REFRESH: {
        Com<ID2D1PathGeometry> g;
        d2d->CreatePathGeometry(&g);
        Com<ID2D1GeometrySink> s;
        g->Open(&s);
        s->BeginFigure(D2D1::Point2F(cx + 7, cy - 2), D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddArc(D2D1::ArcSegment(D2D1::Point2F(cx - 6, cy - 4), D2D1::SizeF(7.5f, 7.5f), 0,
                                   D2D1_SWEEP_DIRECTION_COUNTER_CLOCKWISE, D2D1_ARC_SIZE_SMALL));
        s->EndFigure(D2D1_FIGURE_END_OPEN);
        s->BeginFigure(D2D1::Point2F(cx - 7, cy + 2), D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddArc(D2D1::ArcSegment(D2D1::Point2F(cx + 6, cy + 4), D2D1::SizeF(7.5f, 7.5f), 0,
                                   D2D1_SWEEP_DIRECTION_COUNTER_CLOCKWISE, D2D1_ARC_SIZE_SMALL));
        s->EndFigure(D2D1_FIGURE_END_OPEN);
        s->Close();
        R.rt->DrawGeometry(g, R.br, 1.6f);
        line(cx + 7, cy - 2, cx + 7, cy - 7, c); line(cx + 7, cy - 2, cx + 2, cy - 2, c);
        line(cx - 7, cy + 2, cx - 7, cy + 7, c); line(cx - 7, cy + 2, cx - 2, cy + 2, c);
        break;
    }
    case I_AA:
        text(L"A", cx - 10, cy - 12, 14, 18, c, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        text(L"a", cx + 1, cy - 7, 12, 13, c, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        break;
    case I_TRASH:
        line(cx - 7, cy - 5, cx + 7, cy - 5, c);
        line(cx - 2.5f, cy - 8, cx + 2.5f, cy - 8, c);
        stroke(D2D1::RectF(cx - 5, cy - 5, cx + 5, cy + 7), c, 1.6f, 1.5f);
        line(cx - 1.7f, cy - 2, cx - 1.7f, cy + 4, c, 1.2f); line(cx + 1.7f, cy - 2, cx + 1.7f, cy + 4, c, 1.2f);
        break;
    case I_FOLDER:
        stroke(D2D1::RectF(cx - 8, cy - 5, cx + 8, cy + 6), c, 1.5f, 1.5f);
        line(cx - 8, cy - 5, cx - 7, cy - 8, c, 1.5f); line(cx - 7, cy - 8, cx - 1, cy - 8, c, 1.5f);
        line(cx - 1, cy - 8, cx + 1, cy - 5, c, 1.5f);
        break;
    default: break;
    }
}

static void focus_ring(D2D1_RECT_F r, float rad = 4) {
    stroke(D2D1::RectF(r.left - 3, r.top - 3, r.right + 3, r.bottom + 3), alpha(GOLDHI, 0.95f), 2, rad + 3);
}

enum Kind { PRIMARY, SECONDARY, DANGER };
static void button(int id, D2D1_RECT_F r, const std::wstring &label, Kind k = SECONDARY, Icon ic = I_NONE,
                   bool en = true, float size = 18) {
    add(id, r, en);
    bool hov = en && app.hover == id, prs = hov && app.pressed == id;
    if (k == PRIMARY) {
        vgrad(r, D2D1::ColorF(hov ? 0x4a3d26 : 0x3a301f), D2D1::ColorF(hov ? 0x2a2216 : 0x211a11), 3);
        stroke(r, en ? GOLD : alpha(GOLD, 0.35f), 1, 3);
    } else if (k == DANGER) {
        vgrad(r, D2D1::ColorF(hov ? 0x7d2b21 : 0x6a231b), D2D1::ColorF(hov ? 0x5b1e16 : 0x4d1913), 3);
        stroke(r, D2D1::ColorF(hov ? 0xb04634 : 0x9a3a2c), 1, 3);
    } else {
        fill(r, D2D1::ColorF(hov ? 0x1d1914 : 0x14110d), 3);
        stroke(r, D2D1::ColorF(hov ? 0x6a5f4c : 0x4a4337), 1, 3);
    }
    if (prs) fill(r, D2D1::ColorF(0, 0.25f), 3);
    D2D1_COLOR_F tc = !en ? INK3 : (k == DANGER ? D2D1::ColorF(0xf1d9d2) : INK);
    DWRITE_FONT_WEIGHT wt = k == PRIMARY ? DWRITE_FONT_WEIGHT_SEMI_BOLD : DWRITE_FONT_WEIGHT_NORMAL;
    float tw = text_width(label, size, wt);
    float iw = ic ? 30.f : 0.f;
    float x = (r.left + r.right) / 2 - (tw + iw) / 2;
    float cy = (r.top + r.bottom) / 2;
    if (ic) icon(ic, x + 10, cy, en ? (k == DANGER ? D2D1::ColorF(0xf1d9d2) : GOLDHI) : INK3);
    text(label, x + iw, cy - size * 0.68f, tw + 4, size, tc, wt);
    if (focused(id)) focus_ring(r);
}

static void link(int id, float x, float y, const std::wstring &label, float size = 15, Align al = LEFT) {
    float w = text_width(label, size);
    if (al == RIGHT) x -= w;
    D2D1_RECT_F r = D2D1::RectF(x, y, x + w, y + size * 1.4f);
    add(id, r);
    D2D1_COLOR_F c = app.hover == id ? GOLDHI : INK;
    text(label, x, y, w + 4, size, c);
    line(x, y + size * 1.25f, x + w, y + size * 1.25f, alpha(c, 0.7f), 1);
    if (focused(id)) focus_ring(r, 2);
}

static void radio_card(int id, D2D1_RECT_F r, bool on, const std::wstring &title, const std::wstring &sub) {
    add(id, r);
    bool hov = app.hover == id;
    fill(r, on ? D2D1::ColorF(0x1b160f, 0.92f) : D2D1::ColorF(hov ? 0x15120e : 0x0f0d0a, 0.9f), 4);
    stroke(r, on ? GOLD : D2D1::ColorF(hov ? 0x5a5142 : 0x3a342b), 1, 4);
    float cx = r.left + 22, cy = r.top + 26;
    R.br->SetColor(on ? GOLDHI : INK2);
    R.rt->DrawEllipse(D2D1::Ellipse(D2D1::Point2F(cx, cy), 7.5f, 7.5f), R.br, 1.4f);
    if (on) R.rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(cx, cy), 4, 4), R.br);
    text(title, r.left + 40, r.top + 12, r.right - r.left - 52, 18.5f, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
    text(sub, r.left + 40, r.top + 38, r.right - r.left - 52, 15, INK2);
    if (focused(id)) focus_ring(r, 4);
}

static void check_icon(float cx, float cy, float rad, D2D1_COLOR_F c) {
    R.br->SetColor(c);
    R.rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(cx, cy), rad, rad), R.br);
    line(cx - rad * 0.45f, cy, cx - rad * 0.1f, cy + rad * 0.38f, BG, 2.2f);
    line(cx - rad * 0.1f, cy + rad * 0.38f, cx + rad * 0.5f, cy - rad * 0.35f, BG, 2.2f);
}

static void flag(float x, float y, float w, float h) {
    fill(D2D1::RectF(x, y, x + w, y + h), D2D1::ColorF(0x1e9447), 2);
    Com<ID2D1PathGeometry> g;
    d2d->CreatePathGeometry(&g);
    Com<ID2D1GeometrySink> s;
    g->Open(&s);
    s->BeginFigure(D2D1::Point2F(x + w / 2, y + h * 0.1f), D2D1_FIGURE_BEGIN_FILLED);
    s->AddLine(D2D1::Point2F(x + w * 0.92f, y + h / 2));
    s->AddLine(D2D1::Point2F(x + w / 2, y + h * 0.9f));
    s->AddLine(D2D1::Point2F(x + w * 0.08f, y + h / 2));
    s->EndFigure(D2D1_FIGURE_END_CLOSED);
    s->Close();
    R.br->SetColor(D2D1::ColorF(0xf7d116));
    R.rt->FillGeometry(g, R.br);
    R.br->SetColor(D2D1::ColorF(0x26357f));
    R.rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(x + w / 2, y + h / 2), h * 0.24f, h * 0.24f), R.br);
    line(x + w / 2 - h * 0.23f, y + h / 2 - 1, x + w / 2 + h * 0.23f, y + h / 2 + 1.5f, D2D1::ColorF(0xf2f2f2), 1.2f);
}

// ---------------------------------------------------------------------------------------------------------- screens
static std::wstring target_name() { return app.target_rpcs3 ? L"RPCS3" : L"Soulbrandt"; }
static std::wstring target_path() { return app.target_rpcs3 ? app.rp_game : app.sb_program; }
static bool target_installed() { return app.target_rpcs3 ? app.rp_installed : app.sb_installed; }
static std::wstring installed_fonts() { return app.target_rpcs3 ? app.rp_fonts : app.sb_fonts; }
static std::wstring installed_font_or_original() { std::wstring f = installed_fonts(); return f.empty() ? L"original" : f; }
static const wchar_t *font_label(const std::wstring &f) {
    return f == L"novas" ? L"Fontes HD (fonte nova)" : f == L"hd" ? L"Fontes HD (versão 0.1.1)" : L"Fontes originais";
}

static void draw_hero(ULONGLONG now) {
    float ease = app.art_ready && R.art_loaded ? smooth((now - app.art_t) / 700.f) : 0;
    if (!R.heroes.empty() && ease > 0) {
        int n = (int)R.heroes.size();
        float f = 0;
        if (app.hero_fade_t) f = smooth((now - app.hero_fade_t) / 1500.f);
        R.rt->DrawBitmap(R.heroes[app.hero % n], D2D1::RectF(0, 0, WIN_W, HERO_H), ease);
        if (f > 0) R.rt->DrawBitmap(R.heroes[app.hero_next % n], D2D1::RectF(0, 0, WIN_W, HERO_H), ease * f);
    }
    if (R.logo && ease > 0) {
        D2D1_SIZE_F s = R.logo->GetSize();
        float w = 210, h = w * s.height / s.width;
        R.rt->DrawBitmap(R.logo, D2D1::RectF(44, 42, 44 + w, 42 + h), ease);
    }
    if (ease < 1) {   // wordmark while the art is not there (or for good, when there is no game)
        text(L"Demon's Souls", 46, 58, 400, 42, alpha(INK, 1 - ease), DWRITE_FONT_WEIGHT_NORMAL, LEFT, 80, false, 1.5f);
    }
    flag(44, 138, 34, 22);
    text(L"Tradução para o português do Brasil", 90, 135, 500, 18, INK2);
}

static void draw_titlebar() {
    text(L"Tradução PT-BR · Demon's Souls", 14, 7, 400, 14.5f, INK3);
    D2D1_RECT_F mn = D2D1::RectF(WIN_W - 92, 0, WIN_W - 46, 32), cl = D2D1::RectF(WIN_W - 46, 0, WIN_W, 32);
    add(ID_MIN, mn);
    add(ID_CLOSE, cl);
    if (app.hover == ID_MIN) fill(mn, D2D1::ColorF(1, 1, 1, 0.08f));
    if (app.hover == ID_CLOSE) fill(cl, D2D1::ColorF(0xa33a2a, 0.9f));
    line(WIN_W - 75, 16, WIN_W - 63, 16, INK, 1.3f);
    line(WIN_W - 29, 10, WIN_W - 17, 22, INK, 1.3f);
    line(WIN_W - 17, 10, WIN_W - 29, 22, INK, 1.3f);
}

static void draw_footer() {
    text(L"v0.1.2 · Feito por Fábio (StarKillerChief)", 22, 532, 420, 14.5f, INK3);
    link(ID_ABOUT, WIN_W - 22, 530, L"Sobre", 15, RIGHT);
    float w = text_width(L"Sobre", 15);
    text(L"·", WIN_W - 22 - w - 22, 530, 12, 15, INK3);
    link(ID_GITHUB, WIN_W - 22 - w - 32, 530, L"GitHub", 15, RIGHT);
}

static void sheet_title(const std::wstring &t, const std::wstring &sub, float y = 230) {
    text(t, SHEET_X, y, SHEET_W, 25, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
    if (!sub.empty()) text(sub, SHEET_X, y + 36, SHEET_W, 16.5f, INK2);
}

static void font_cards(float y) {
    text(L"FONTE DO TEXTO", SHEET_X, y, 300, 14.5f, GOLD, DWRITE_FONT_WEIGHT_SEMI_BOLD, LEFT, 30, false, 1.5f);
    float w = (SHEET_W - 10) / 2;
    radio_card(ID_FONT_ORIG, D2D1::RectF(SHEET_X, y + 22, SHEET_X + w, y + 100), app.font != L"novas",
               L"Fontes originais", L"Como no jogo do PS3, já com os acentos do português.");
    radio_card(ID_FONT_NEW, D2D1::RectF(SHEET_X + w + 10, y + 22, SHEET_X + SHEET_W, y + 100), app.font == L"novas",
               L"Fontes HD", L"Uma fonte nova, de letras nítidas, com negrito nos diálogos.");
}

static void draw_home(bool change_font) {
    float y = 232;
    if (!change_font) {
        D2D1_RECT_F row = D2D1::RectF(SHEET_X, y, SHEET_X + SHEET_W, y + 42);
        fill(row, PANEL, 3);
        stroke(row, LINE, 1, 3);
        R.br->SetColor(OK);
        D2D1_POINT_2F c = D2D1::Point2F(SHEET_X + 17, y + 21);
        R.rt->SetTransform(D2D1::Matrix3x2F::Rotation(45, c));
        R.rt->FillRectangle(D2D1::RectF(c.x - 3.5f, c.y - 3.5f, c.x + 3.5f, c.y + 3.5f), R.br);
        R.rt->SetTransform(D2D1::Matrix3x2F::Identity());
        float tw = text_width(target_name(), 17.5f, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        text(target_name(), SHEET_X + 30, y + 9, tw + 10, 17.5f, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        std::wstring p = target_path();
        if (p.size() > 52) p = L"…" + p.substr(p.size() - 51);
        text(p, SHEET_X + 42 + tw, y + 11, SHEET_W - tw - 150, 15, INK3);
        link(ID_CHANGE, SHEET_X + SHEET_W - 16, y + 9, L"Mudar", 17, RIGHT);
        font_cards(y + 56);
    } else {
        sheet_title(L"Trocar fonte", L"A tradução é montada de novo com a fonte escolhida.");
        font_cards(y + 70);
    }
    float by = 475;
    if (!change_font) {
        text(L"ⓘ", SHEET_X, y + 168, 20, 16, INK3);
        std::wstring inc = app.target_rpcs3 ? L"Inclui: textos, fontes com acentos, letreiros e as 17 telas de carregamento."
                                            : L"Inclui: textos, fontes com acentos, letreiros, 17 telas de carregamento e legendas dos filmes.";
        text(inc, SHEET_X + 22, y + 168, SHEET_W - 22, 15, INK2);
        button(ID_INSTALL, D2D1::RectF(SHEET_X, by, SHEET_X + 184, by + 42), L"Instalar tradução", PRIMARY);
        text(L"Leva até 1 minuto.", SHEET_X + 200, by + 12, 300, 15, INK3);
    } else {
        button(ID_APPLY, D2D1::RectF(SHEET_X, by, SHEET_X + 160, by + 42), L"Aplicar", PRIMARY);
        link(ID_BACK, SHEET_X + 184, by + 10, L"Voltar", 17);
    }
}

static void draw_targets() {
    sheet_title(L"Onde instalar a tradução?", L"");
    float y = 280, w = (SHEET_W - 10) / 2;
    std::wstring sb = app.sb_found ? (app.sb_prepared ? L"Encontrado. Tradução completa, com legendas dos filmes."
                                                      : L"Encontrado, mas ainda não preparado.")
                                   : L"Não encontrado perto desta pasta.";
    radio_card(ID_T_SB, D2D1::RectF(SHEET_X, y, SHEET_X + w, y + 92), !app.target_pick_rpcs3, L"Soulbrandt", sb);
    radio_card(ID_T_RP, D2D1::RectF(SHEET_X + w + 10, y, SHEET_X + SHEET_W, y + 92), app.target_pick_rpcs3,
               L"RPCS3 (emulador de PS3)", L"Textos e imagens traduzidos. As legendas dos filmes só no Soulbrandt.");
    float by = 475;
    bool en = app.target_pick_rpcs3 || (app.sb_found && app.sb_prepared);
    button(ID_T_CONTINUE, D2D1::RectF(SHEET_X, by, SHEET_X + 160, by + 42), L"Continuar", PRIMARY, I_NONE, en);
    link(ID_BACK, SHEET_X + 184, by + 10, L"Voltar", 17);
}

static void draw_rpcs3() {
    sheet_title(L"Pasta do jogo no RPCS3", L"Escolha a pasta do Demon's Souls (BLUS30443) no RPCS3.");
    float y = 300;
    D2D1_RECT_F box = D2D1::RectF(SHEET_X, y, SHEET_X + SHEET_W - 150, y + 44);
    fill(box, D2D1::ColorF(0x0b0907), 3);
    stroke(box, app.rp_check == -1 ? ERR : D2D1::ColorF(0x4a4337), 1, 3);
    std::wstring p = app.rp_game.empty() ? L"Nenhuma pasta escolhida" : app.rp_game;
    if (p.size() > 56) p = L"…" + p.substr(p.size() - 55);
    text(p, SHEET_X + 14, y + 11, SHEET_W - 180, 15.5f, app.rp_game.empty() ? INK3 : INK);
    button(ID_BROWSE, D2D1::RectF(SHEET_X + SHEET_W - 138, y, SHEET_X + SHEET_W, y + 44), L"Procurar...",
           app.rp_check == -1 ? PRIMARY : SECONDARY, I_FOLDER);
    float ly = y + 56;
    if (app.rp_check == 1) {
        check_icon(SHEET_X + 9, ly + 11, 8, OK);
        text(L"Jogo encontrado: Demon's Souls (BLUS30443)", SHEET_X + 24, ly, SHEET_W, 16, OK);
    } else if (app.rp_check == -1) {
        text(L"✕  " + app.rp_msg, SHEET_X, ly, SHEET_W, 15.5f, ERR);
    } else if (app.rp_check == 2) {
        text(L"Conferindo a pasta...", SHEET_X, ly, SHEET_W, 15.5f, INK2);
    } else {
        text(L"Não encontrei o jogo no RPCS3 sozinho. Clique em Procurar... e escolha a pasta.", SHEET_X, ly, SHEET_W, 15.5f, INK2);
    }
    text(L"Dica: no RPCS3, clique com o botão direito no jogo e escolha Abrir pasta do jogo. "
         L"Pode escolher essa pasta ou qualquer pasta dentro dela.", SHEET_X, ly + 34, SHEET_W, 15, INK3);
    text(L"No RPCS3 os filmes ficam sem legendas (elas só funcionam no Soulbrandt).", SHEET_X, ly + 76, SHEET_W, 15, INK3);
    float by = 475;
    button(ID_RP_CONTINUE, D2D1::RectF(SHEET_X, by, SHEET_X + 160, by + 42), L"Continuar", PRIMARY, I_NONE, app.rp_check == 1);
    link(ID_BACK, SHEET_X + 184, by + 10, L"Voltar", 17);
}

struct StepRow { const char *key; const wchar_t *label; };

static void draw_installing(ULONGLONG now) {
    bool un = app.uninstalling;
    sheet_title(un ? L"Desinstalando a tradução..." : L"Instalando a tradução...", L"");
    std::wstring cur;
    std::vector<StepRow> rows;
    if (un) rows = {{"prepare", L"Restaurando os arquivos originais"}, {"done", L"Finalizando"}};
    else {
        rows = {{"prepare", L"Preparando a pasta"}, {"fonts", L"Fontes com acentos"}, {"text", L"Texto do jogo"},
                {"banners", L"Letreiros"}, {"loading", L"Telas de carregamento"}};
        if (!app.target_rpcs3) rows.push_back({"subs", L"Legendas dos filmes"});
        rows.push_back({"writing", L"Finalizando"});
    }
    int cur_i = 0;
    for (int i = 0; i < (int)rows.size(); i++)
        if (app.step == rows[i].key || (app.step == "folder" && std::string(rows[i].key) == "prepare")) cur_i = i;
    if (app.step == "done") cur_i = (int)rows.size();
    std::wstring label = cur_i < (int)rows.size() ? rows[cur_i].label : L"Pronto";
    if (cur_i < (int)rows.size() && std::string(rows[cur_i].key) == "loading" && app.loading_n)
        label += L" (" + std::to_wstring(app.loading_n) + L" de 17)";
    text(label + L"...", SHEET_X, 268, SHEET_W, 16.5f, INK2);
    float by = 302;
    D2D1_RECT_F bar = D2D1::RectF(SHEET_X, by, SHEET_X + SHEET_W, by + 8);
    fill(bar, D2D1::ColorF(0x1c1813), 4);
    if (un) {
        float t = fmodf(now / 1400.f, 1.f), x0 = SHEET_X + (SHEET_W - 160) * t;
        vgrad(D2D1::RectF(x0, by, x0 + 160, by + 8), GOLDHI, GOLD, 4);
    } else {
        vgrad(D2D1::RectF(SHEET_X, by, SHEET_X + SHEET_W * app.pct / 100.f, by + 8), GOLDHI, GOLD, 4);
        text(std::to_wstring(app.pct) + L"%", SHEET_X, by + 14, 100, 15, INK2);
        float el = (now - app.t_start) / 1000.f;
        if (app.pct > 8 && app.pct < 100) {
            int rem = (int)std::max(1.f, el * (100 - app.pct) / app.pct);
            text(L"cerca de " + std::to_wstring(rem) + L" s", SHEET_X, by + 14, SHEET_W, 15, INK2, DWRITE_FONT_WEIGHT_NORMAL, RIGHT);
        }
    }
    float ry = 348;
    int half = ((int)rows.size() + 1) / 2;
    for (int i = 0; i < (int)rows.size(); i++) {
        float x = SHEET_X + (i < half ? 0 : SHEET_W / 2), y = ry + (i % half) * 28;
        std::wstring l = rows[i].label;
        if (std::string(rows[i].key) == "loading" && i == cur_i && app.loading_n)
            l += L" " + std::to_wstring(app.loading_n) + L"/17";
        if (i < cur_i) { check_icon(x + 8, y + 11, 7.5f, OK); text(l, x + 24, y, 300, 16, INK2); }
        else if (i == cur_i) {
            R.br->SetColor(GOLDHI);
            float a = now / 180.f;
            for (int k = 0; k < 8; k++) {
                float an = a + k * 0.785f;
                R.br->SetOpacity(0.25f + 0.75f * k / 8.f);
                R.rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(x + 8 + 6 * cosf(an), y + 11 + 6 * sinf(an)), 1.4f, 1.4f), R.br);
            }
            R.br->SetOpacity(1);
            text(l, x + 24, y, 300, 16, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        } else {
            R.br->SetColor(INK3);
            R.rt->DrawEllipse(D2D1::Ellipse(D2D1::Point2F(x + 8, y + 11), 6.5f, 6.5f), R.br, 1.2f);
            text(l, x + 24, y, 300, 16, INK3);
        }
    }
    D2D1_RECT_F note = D2D1::RectF(SHEET_X, 462, SHEET_X + SHEET_W, 504);
    fill(note, D2D1::ColorF(0x14110c, 0.95f), 3);
    stroke(note, D2D1::ColorF(0x4a4030), 1, 3);
    text(L"Não feche esta janela até terminar. Isso leva até 1 minuto.", SHEET_X + 18, 473, SHEET_W - 30, 15.5f, INK);
}

static void draw_installed() {
    sheet_title(app.done_fresh ? L"Pronto! A tradução está instalada" : L"A tradução está instalada",
                app.target_rpcs3 ? L"Abra o jogo no RPCS3 normalmente e jogue em português."
                                 : L"Abra o Soulbrandt normalmente e jogue em português.");
    check_icon(SHEET_X - 22, 248, 11, OK);
    float y = 292;
    D2D1_RECT_F box = D2D1::RectF(SHEET_X, y, SHEET_X + SHEET_W, y + 68);
    fill(box, PANEL, 3);
    stroke(box, LINE, 1, 3);
    auto kv = [&](float x, float yy, const wchar_t *k, const std::wstring &v) {
        text(k, x, yy, 80, 15, INK3);
        text(v, x + 66, yy, 270, 15.5f, INK);
    };
    kv(SHEET_X + 14, y + 11, L"Versão", L"Tradução PT-BR v0.1.2");
    kv(SHEET_X + 14, y + 37, L"Destino", target_name());
    kv(SHEET_X + 344, y + 11, L"Fontes", font_label(installed_fonts()));
    kv(SHEET_X + 344, y + 37, L"Filmes", app.target_rpcs3 ? L"Sem legendas (só no Soulbrandt)"
                                                  : app.sb_subs ? L"Com legendas" : L"Sem legendas: clique em Reinstalar");
    float by = 374, bw = (SHEET_W - 20) / 3, bh = 52;
    if (app.target_rpcs3) button(ID_EXIT, D2D1::RectF(SHEET_X, by, SHEET_X + bw, by + bh), L"Fechar", PRIMARY, I_X);
    else button(ID_OPEN, D2D1::RectF(SHEET_X, by, SHEET_X + bw, by + bh), L"Abrir Soulbrandt", PRIMARY, I_PLAY);
    button(ID_REINSTALL, D2D1::RectF(SHEET_X + bw + 10, by, SHEET_X + 2 * bw + 10, by + bh), L"Reinstalar", SECONDARY, I_REFRESH);
    button(ID_CHANGEFONT, D2D1::RectF(SHEET_X + 2 * bw + 20, by, SHEET_X + SHEET_W, by + bh), L"Trocar fonte", SECONDARY, I_AA);
    button(ID_UNINSTALL, D2D1::RectF(SHEET_X, by + bh + 10, SHEET_X + SHEET_W, by + 2 * bh + 10), L"Desinstalar", DANGER, I_TRASH);
}

static void draw_uninstalled() {
    sheet_title(L"A tradução foi removida", L"O jogo voltou ao inglês. Seus saves não foram alterados.");
    check_icon(SHEET_X - 22, 248, 11, OK);
    float by = 330;
    button(ID_INSTALL_AGAIN, D2D1::RectF(SHEET_X, by, SHEET_X + 210, by + 46), L"Instalar de novo", PRIMARY, I_REFRESH);
    button(ID_EXIT, D2D1::RectF(SHEET_X + 222, by, SHEET_X + 382, by + 46), L"Fechar", SECONDARY, I_X);
}

static void draw_error() {
    sheet_title(app.err_title, L"");
    text(L"!", SHEET_X - 26, 232, 20, 24, ERR, DWRITE_FONT_WEIGHT_BOLD, CENTER);
    float h = text(app.err_msg, SHEET_X, 276, SHEET_W, 17, INK2);
    float by = std::max(360.f, 290 + h + 30);
    button(ID_RETRY, D2D1::RectF(SHEET_X, by, SHEET_X + 190, by + 44), L"Tentar de novo", PRIMARY, I_REFRESH);
    if (app.err_code == L"not_prepared" || app.err_code == L"no_soulbrandt")
        button(ID_CHOOSE_RP, D2D1::RectF(SHEET_X + 202, by, SHEET_X + 432, by + 44), L"Usar o RPCS3", SECONDARY);
    else if (app.err_code == L"failed" || app.err_code == L"crash" || app.err_code == L"uninstall")
        link(ID_LOG, SHEET_X + 214, by + 11, L"Abrir o registro", 16);
}

static void draw_notfound() {
    sheet_title(L"Não encontrei o jogo", L"");
    text(L"Coloque a pasta PT-BR dentro da pasta do Soulbrandt (ao lado do Soulbrandt.exe), "
         L"ou escolha a pasta do Demon's Souls no RPCS3.", SHEET_X, 276, SHEET_W, 17, INK2);
    float by = 360;
    button(ID_CHOOSE_RP, D2D1::RectF(SHEET_X, by, SHEET_X + 250, by + 44), L"Escolher pasta no RPCS3", PRIMARY, I_FOLDER);
    button(ID_RETRY, D2D1::RectF(SHEET_X + 262, by, SHEET_X + 452, by + 44), L"Procurar de novo", SECONDARY, I_REFRESH);
}

static void draw_modal() {
    if (app.modal == M_NONE) return;
    items.clear();                                // only the dialog takes input
    fill(D2D1::RectF(0, 0, WIN_W, WIN_H), D2D1::ColorF(0, 0.62f));
    if (app.modal == M_CONFIRM) {
        D2D1_RECT_F d = D2D1::RectF(250, 170, 710, 380);
        fill(d, D2D1::ColorF(0x100d0a), 4);
        stroke(d, D2D1::ColorF(0x5a4f3e), 1, 4);
        text(L"Desinstalar a tradução?", 278, 194, 400, 23, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        text(L"O jogo volta ao inglês. Seus saves não são alterados, e você pode instalar de novo quando quiser.",
             278, 236, 404, 16.5f, INK2);
        button(ID_M_CANCEL, D2D1::RectF(278, 318, 470, 360), L"Cancelar", SECONDARY);
        button(ID_M_OK, D2D1::RectF(490, 318, 682, 360), L"Desinstalar", DANGER, I_TRASH);
    } else if (app.modal == M_SAMEFONT) {
        D2D1_RECT_F d = D2D1::RectF(250, 170, 710, 380);
        fill(d, D2D1::ColorF(0x100d0a), 4);
        stroke(d, D2D1::ColorF(0x5a4f3e), 1, 4);
        std::wstring f = installed_fonts();
        text(f == L"novas" ? L"As fontes HD já estão instaladas" : f == L"hd" ? L"As fontes HD já estão instaladas"
                           : L"As fontes originais já estão instaladas",
             278, 194, 404, 23, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        text(L"Não é preciso fazer nada. Reinstale só se algo parecer errado no jogo.",
             278, 236, 404, 16.5f, INK2);
        button(ID_M_CANCEL, D2D1::RectF(278, 318, 470, 360), L"Cancelar", SECONDARY);
        button(ID_M_REINSTALL, D2D1::RectF(490, 318, 682, 360), L"Reinstalar", PRIMARY, I_REFRESH);
    } else {
        D2D1_RECT_F d = D2D1::RectF(170, 70, 790, 500);
        fill(d, D2D1::ColorF(0x100d0a), 4);
        stroke(d, D2D1::ColorF(0x5a4f3e), 1, 4);
        text(L"Sobre", 198, 92, 400, 24, INK, DWRITE_FONT_WEIGHT_SEMI_BOLD);
        float y = 134;
        const wchar_t *lines[] = {
            L"Tradução PT-BR de Demon's Souls, versão 0.1.2.",
            L"Tradução e ferramentas: Fábio (StarKillerChief), com ajuda do Claude (IA da Anthropic).",
            L"Projeto sem fins lucrativos. Tudo é gerado no seu PC, a partir da sua própria cópia do jogo: "
            L"este programa não traz nenhum arquivo do jogo.",
            L"Fonte das telas e desta janela: EB Garamond (SIL Open Font License).",
            L"Soulbrandt é um projeto de outro autor. Demon's Souls é marca da Sony Interactive Entertainment e da "
            L"FromSoftware. Esta tradução não é oficial."};
        for (auto l : lines) y += text(l, 198, y, 564, 15.5f, INK2) + 12;
        button(ID_M_CLOSE, D2D1::RectF(198, 440, 358, 480), L"Fechar", PRIMARY);
        link(ID_GITHUB, 380, 450, L"Abrir o GitHub", 16);
    }
}

static void paint(ULONGLONG now) {
    items.clear();
    R.rt->Clear(BG);
    ensure_art();
    draw_hero(now);
    draw_titlebar();
    switch (app.screen) {
    case S_LOADING: text(L"Procurando o jogo...", SHEET_X, 300, SHEET_W, 17, INK2); break;
    case S_HOME: draw_home(false); break;
    case S_FONTCHANGE: draw_home(true); break;
    case S_TARGETS: draw_targets(); break;
    case S_RPCS3: draw_rpcs3(); break;
    case S_INSTALLING: case S_UNINSTALLING: draw_installing(now); break;
    case S_INSTALLED: draw_installed(); break;
    case S_UNINSTALLED: draw_uninstalled(); break;
    case S_ERROR: draw_error(); break;
    case S_NOTFOUND: draw_notfound(); break;
    }
    draw_footer();
    draw_modal();
}

// ---------------------------------------------------------------------------------------------------------- logic
static void apply_state(const JVal &st) {
    const JVal &sb = st["soulbrandt"];
    app.sb_found = sb["found"].truthy();
    app.sb_prepared = sb["prepared"].truthy();
    app.sb_running = sb["running"].truthy();
    app.sb_installed = sb["installed"].truthy();
    app.sb_subs = sb["subs"].truthy();
    app.sb_program = W(sb["program"].str());
    app.sb_game = W(sb["game"].str());
    app.sb_fonts = W(sb["fonts"].str("original"));
    const JVal &c = st["rpcs3"]["candidates"];
    std::wstring remembered = app.rp_game;
    bool picked = false;
    for (auto &v : c.a) {
        std::wstring g = W(v["game"].str());
        if (remembered.empty() || _wcsicmp(g.c_str(), remembered.c_str()) == 0) {
            app.rp_game = g;
            app.rp_installed = v["installed"].truthy();
            app.rp_fonts = W(v["fonts"].str("original"));
            app.rp_check = 1;
            picked = true;
            break;
        }
    }
    if (!picked && !remembered.empty()) { app.rp_check = 2; run_backend(J_VALIDATE, L"validate --game " + q(remembered)); }
    if (!app.sb_found || !app.sb_prepared) {
        if (!app.rp_game.empty()) app.target_rpcs3 = true;
    }
    if (app.target_rpcs3 && app.rp_game.empty()) app.target_rpcs3 = false;
    if (!app.target_rpcs3 && !(app.sb_found && app.sb_prepared)) {
        if (app.sb_found) {
            app.screen = S_ERROR;
            app.err_code = L"not_prepared";
            app.err_title = L"O Soulbrandt ainda não foi preparado";
            app.err_msg = L"Abra o Soulbrandt.exe uma vez, deixe ele preparar o jogo até o fim e feche. Depois clique em Tentar de novo.";
        } else app.screen = S_NOTFOUND;
    } else {
        app.screen = target_installed() ? S_INSTALLED : S_HOME;
        app.font = target_installed() ? installed_font_or_original() : L"original";
    }
    app.done_fresh = false;
    start_art();
}

static int step_pct(const std::string &s, int n) {
    bool rp = app.target_rpcs3;
    if (s == "prepare") return 3;
    if (s == "folder") return 8;
    if (s == "fonts") return 14;
    bool big = app.font != L"original";
    if (s == "text") return big ? 40 : 34;
    if (s == "banners") return big ? 50 : 46;
    if (s == "loading") return (big ? 50 : 46) + n * (rp ? 38 : 32) / 17;
    if (s == "writing") return rp ? 92 : 84;
    if (s == "subs") return 92;
    if (s == "done") return 100;
    return app.pct;
}

static void on_line(int kind, const std::string &l) {
    if (kind == J_STATE) {
        JVal v;
        if (parse_json(l, v) && v.kind == JVal::Obj && v.o.count("soulbrandt")) apply_state(v);
        return;
    }
    if (l.size() < 3 || l[0] != '@' || l[1] != '@') return;
    JVal v;
    if (!parse_json(l.substr(2), v)) return;
    std::string st = v["step"].str();
    if (kind == J_ART) {
        if (st == "done") { app.art_ready = true; app.art_t = GetTickCount64(); R.art_loaded = false; }
        return;
    }
    if (kind == J_VALIDATE) {
        if (st == "done") {
            app.rp_check = 1;
            app.rp_installed = v["installed"].truthy();
            app.rp_fonts = W(v["fonts"].str("original"));
        } else if (st == "error") { app.rp_check = -1; app.rp_msg = W(v["message"].str()); }
        return;
    }
    if (st == "error") {
        app.err_code = W(v["code"].str());
        app.err_msg = W(v["message"].str());
        if (app.err_code == L"running") app.err_title = L"O Soulbrandt está aberto";
        else if (app.err_code == L"not_prepared") app.err_title = L"O Soulbrandt ainda não foi preparado";
        else if (app.err_code == L"wrong_version") app.err_title = L"Versão do jogo diferente";
        else if (app.err_code == L"not_game") app.err_title = L"Pasta do jogo não encontrada";
        else {
            app.err_title = app.uninstalling ? L"A desinstalação não terminou" : L"A instalação não terminou";
            if (!app.uninstalling) app.err_msg += L"\n\nNada foi alterado: o jogo continua como estava.";
        }
        app.screen = S_ERROR;
        app.busy = false;
        return;
    }
    if (st == "loading") app.loading_n = v["n"].num();
    app.step = st;
    app.pct = std::max(app.pct, step_pct(st, app.loading_n));
    if (st == "done" && (kind == J_INSTALL || kind == J_UNINSTALL)) {
        app.busy = false;
        if (kind == J_INSTALL) {
            if (app.target_rpcs3) { app.rp_installed = true; app.rp_fonts = app.font; }
            else { app.sb_installed = true; app.sb_subs = true; app.sb_fonts = app.font; }
            app.done_fresh = true;
            app.screen = S_INSTALLED;
        } else {
            if (app.target_rpcs3) app.rp_installed = false; else app.sb_installed = false;
            app.screen = S_UNINSTALLED;
        }
        app.focus = 0;
    }
}

static void on_exit(int kind, DWORD code) {
    if ((kind == J_INSTALL || kind == J_UNINSTALL) && app.busy) {   // ended without a done/error line
        app.busy = false;
        app.err_code = L"crash";
        app.err_title = kind == J_INSTALL ? L"A instalação não terminou" : L"A desinstalação não terminou";
        app.err_msg = L"O instalador parou sem terminar (código " + std::to_wstring(code) + L"). Veja o registro.";
        app.screen = S_ERROR;
    }
    if (kind == J_STATE && app.screen == S_LOADING) app.screen = S_NOTFOUND;
}

static bool pick_folder(std::wstring &out) {
    Com<IFileOpenDialog> d;
    if (FAILED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&d)))) return false;
    DWORD o = 0;
    d->GetOptions(&o);
    d->SetOptions(o | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM);
    d->SetTitle(L"Pasta do Demon's Souls (BLUS30443) no RPCS3");
    if (FAILED(d->Show(app.hwnd))) return false;
    Com<IShellItem> it;
    if (FAILED(d->GetResult(&it))) return false;
    wchar_t *p = nullptr;
    if (FAILED(it->GetDisplayName(SIGDN_FILESYSPATH, &p))) return false;
    out = p;
    CoTaskMemFree(p);
    return true;
}

static void refresh_state() {
    app.screen = S_LOADING;
    run_backend(J_STATE, L"state");
}

static void action(int id) {
    switch (id) {
    case ID_MIN: ShowWindow(app.hwnd, SW_MINIMIZE); break;
    case ID_CLOSE: case ID_EXIT: PostMessageW(app.hwnd, WM_CLOSE, 0, 0); break;
    case ID_GITHUB: ShellExecuteW(nullptr, L"open", GITHUB, nullptr, nullptr, SW_SHOWNORMAL); break;
    case ID_ABOUT: app.modal = M_ABOUT; app.focus = ID_M_CLOSE; break;
    case ID_M_CLOSE: case ID_M_CANCEL: app.modal = M_NONE; app.focus = 0; break;
    case ID_M_OK: start_install(true); break;
    case ID_CHANGE: app.target_pick_rpcs3 = app.target_rpcs3; app.screen = S_TARGETS; app.focus = 0; break;
    case ID_FONT_ORIG: app.font = L"original"; break;
    case ID_FONT_NEW: app.font = L"novas"; break;
    case ID_INSTALL: start_install(false); break;
    case ID_APPLY:
        if (target_installed() && installed_font_or_original() == app.font) {
            app.modal = M_SAMEFONT; app.focus = ID_M_CANCEL; app.kb_focus = true;
        } else start_install(false);
        break;
    case ID_M_REINSTALL: start_install(false); break;
    case ID_REINSTALL: app.font = installed_font_or_original(); start_install(false); break;
    case ID_CHANGEFONT: app.font = installed_font_or_original() == L"novas" ? L"original" : L"novas"; app.screen = S_FONTCHANGE; app.focus = 0; break;
    case ID_UNINSTALL: app.modal = M_CONFIRM; app.focus = ID_M_CANCEL; app.kb_focus = true; break;
    case ID_T_SB: app.target_pick_rpcs3 = false; break;
    case ID_T_RP: app.target_pick_rpcs3 = true; break;
    case ID_T_CONTINUE:
        if (app.target_pick_rpcs3) { app.screen = S_RPCS3; }
        else { app.target_rpcs3 = false; save_prefs(); app.screen = app.sb_installed ? S_INSTALLED : S_HOME; }
        app.focus = 0;
        break;
    case ID_CHOOSE_RP: app.screen = S_RPCS3; app.focus = 0; break;
    case ID_BROWSE: {
        std::wstring p;
        if (pick_folder(p)) { app.rp_game = p; app.rp_check = 2; run_backend(J_VALIDATE, L"validate --game " + q(p)); }
        break;
    }
    case ID_RP_CONTINUE:
        app.target_rpcs3 = true;
        save_prefs();
        app.screen = app.rp_installed ? S_INSTALLED : S_HOME;
        app.font = app.rp_installed && !app.rp_fonts.empty() ? app.rp_fonts : L"original";
        if (!app.art_ready) start_art();
        app.focus = 0;
        break;
    case ID_BACK:
        app.screen = target_installed() ? S_INSTALLED : ((app.sb_found && app.sb_prepared) || app.target_rpcs3 ? S_HOME : S_NOTFOUND);
        app.focus = 0;
        break;
    case ID_OPEN:
        ShellExecuteW(nullptr, L"open", (app.sb_program + L"\\Soulbrandt.exe").c_str(), nullptr, app.sb_program.c_str(), SW_SHOWNORMAL);
        PostMessageW(app.hwnd, WM_CLOSE, 0, 0);
        break;
    case ID_RETRY: refresh_state(); break;
    case ID_LOG: ShellExecuteW(nullptr, L"open", path(L"cache\\registro.txt").c_str(), nullptr, nullptr, SW_SHOWNORMAL); break;
    case ID_INSTALL_AGAIN: app.screen = S_HOME; app.focus = 0; break;
    }
    InvalidateRect(app.hwnd, nullptr, FALSE);
}

static void escape() {
    if (app.modal) { app.modal = M_NONE; app.focus = 0; }
    else if (app.screen == S_TARGETS || app.screen == S_RPCS3 || app.screen == S_FONTCHANGE) action(ID_BACK);
}

static void move_focus(int dir) {
    std::vector<int> ids;
    for (auto &it : items) if (it.enabled && it.id != ID_MIN && it.id != ID_CLOSE) ids.push_back(it.id);
    if (ids.empty()) return;
    auto p = std::find(ids.begin(), ids.end(), app.focus);
    int i = p == ids.end() ? (dir > 0 ? -1 : 0) : (int)(p - ids.begin());
    app.focus = ids[(i + dir + (int)ids.size()) % ids.size()];
    app.kb_focus = true;
}

// ---------------------------------------------------------------------------------------------------------- window
static float g_scale = 1;

static void create_target(HWND h) {
    if (R.rt) return;
    RECT rc;
    GetClientRect(h, &rc);
    ID2D1HwndRenderTarget *t = nullptr;
    UINT dpi = GetDpiForWindow(h);
    d2d->CreateHwndRenderTarget(D2D1::RenderTargetProperties(D2D1_RENDER_TARGET_TYPE_DEFAULT,
                                    D2D1::PixelFormat(DXGI_FORMAT_UNKNOWN, D2D1_ALPHA_MODE_UNKNOWN), (float)dpi, (float)dpi),
                                D2D1::HwndRenderTargetProperties(h, D2D1::SizeU(rc.right, rc.bottom)), &t);
    R.rt = t;
    R.rt->CreateSolidColorBrush(INK, &R.br);
    R.rt->SetTextAntialiasMode(D2D1_TEXT_ANTIALIAS_MODE_GRAYSCALE);
}

static bool animating(ULONGLONG now) {
    if (app.screen == S_INSTALLING || app.screen == S_UNINSTALLING) return true;
    if (app.art_ready && now - app.art_t < 800) return true;
    if (app.hero_fade_t && now - app.hero_fade_t < 1600) return true;
    return false;
}

static LRESULT CALLBACK wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_NCCALCSIZE: if (wp) return 0; break;
    case WM_NCHITTEST: {
        POINT p{GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
        ScreenToClient(h, &p);
        float x = p.x / g_scale, y = p.y / g_scale;
        if (y < 32 && x < WIN_W - 92) return HTCAPTION;
        return HTCLIENT;
    }
    case WM_PAINT: {
        PAINTSTRUCT ps;
        BeginPaint(h, &ps);
        create_target(h);
        R.rt->BeginDraw();
        paint(GetTickCount64());
        if (R.rt->EndDraw() == D2DERR_RECREATE_TARGET) R.drop();
        EndPaint(h, &ps);
        return 0;
    }
    case WM_TIMER: {
        ULONGLONG now = GetTickCount64();
        if (!app.reduced_motion && R.heroes.size() > 1 && app.art_ready) {
            if (!app.hero_t) app.hero_t = now;
            if (app.hero_fade_t && now - app.hero_fade_t >= 1500) {
                app.hero = app.hero_next;
                app.hero_next = (app.hero + 1) % (int)R.heroes.size();
                app.hero_fade_t = 0;
                app.hero_t = now;
            } else if (!app.hero_fade_t && now - app.hero_t >= 6000) app.hero_fade_t = now;
        }
        if (animating(now)) InvalidateRect(h, nullptr, FALSE);
        return 0;
    }
    case WM_MOUSEMOVE: {
        float x = GET_X_LPARAM(lp) / g_scale, y = GET_Y_LPARAM(lp) / g_scale;
        int hv = 0;
        for (auto &it : items) if (it.enabled && inside(it.r, x, y)) hv = it.id;
        if (hv != app.hover) {
            app.hover = hv;
            InvalidateRect(h, nullptr, FALSE);
        }
        TRACKMOUSEEVENT t{sizeof(t), TME_LEAVE, h, 0};
        TrackMouseEvent(&t);
        SetCursor(LoadCursor(nullptr, hv && hv != ID_MIN && hv != ID_CLOSE ? IDC_HAND : IDC_ARROW));
        return 0;
    }
    case WM_MOUSELEAVE: app.hover = 0; InvalidateRect(h, nullptr, FALSE); return 0;
    case WM_SETCURSOR: if (LOWORD(lp) == HTCLIENT) return TRUE; break;
    case WM_LBUTTONDOWN: app.pressed = app.hover; app.kb_focus = false; SetCapture(h); InvalidateRect(h, nullptr, FALSE); return 0;
    case WM_LBUTTONUP: {
        ReleaseCapture();
        int p = app.pressed;
        app.pressed = 0;
        if (p && p == app.hover) { app.focus = p; action(p); }
        InvalidateRect(h, nullptr, FALSE);
        return 0;
    }
    case WM_KEYDOWN:
        if (wp == VK_TAB) move_focus(GetKeyState(VK_SHIFT) < 0 ? -1 : 1);
        else if (wp == VK_ESCAPE) escape();
        else if (wp == VK_RETURN || wp == VK_SPACE) { if (app.focus) action(app.focus); }
        else if (wp == VK_LEFT || wp == VK_RIGHT || wp == VK_UP || wp == VK_DOWN) {
            if (app.focus == ID_FONT_ORIG || app.focus == ID_FONT_NEW) {
                bool to_new = app.focus == ID_FONT_ORIG;
                app.font = to_new ? L"novas" : L"original"; app.focus = to_new ? ID_FONT_NEW : ID_FONT_ORIG;
            } else if (app.focus == ID_T_SB || app.focus == ID_T_RP) {
                app.target_pick_rpcs3 = !app.target_pick_rpcs3; app.focus = app.target_pick_rpcs3 ? ID_T_RP : ID_T_SB;
            } else move_focus(wp == VK_LEFT || wp == VK_UP ? -1 : 1);
        }
        InvalidateRect(h, nullptr, FALSE);
        return 0;
    case WM_APP_LINE: {
        std::string *s = (std::string *)lp;
        on_line((int)wp, *s);
        delete s;
        InvalidateRect(h, nullptr, FALSE);
        return 0;
    }
    case WM_APP_EXIT: on_exit((int)wp, (DWORD)lp); InvalidateRect(h, nullptr, FALSE); return 0;
    case WM_DPICHANGED: {
        RECT *r = (RECT *)lp;
        g_scale = HIWORD(wp) / 96.f;
        SetWindowPos(h, nullptr, r->left, r->top, r->right - r->left, r->bottom - r->top, SWP_NOZORDER | SWP_NOACTIVATE);
        R.drop();
        InvalidateRect(h, nullptr, FALSE);
        return 0;
    }
    case WM_SIZE: if (R.rt) { R.drop(); } return 0;
    case WM_CLOSE:
        if (app.busy) {
            MessageBoxW(h, L"Espere a instalação terminar antes de fechar. Fechar agora pode deixar o jogo pela metade.",
                        L"Tradução PT-BR", MB_OK | MB_ICONINFORMATION);
            return 0;
        }
        DestroyWindow(h);
        return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

// ---------------------------------------------------------------------------------------------------------- snapshot
static int snapshot(const std::wstring &out, const std::wstring &scr, int hero) {
    const UINT SW_ = (UINT)WIN_W, SH_ = (UINT)WIN_H;
    Com<IWICBitmap> bm;
    wic->CreateBitmap(SW_, SH_, GUID_WICPixelFormat32bppPBGRA, WICBitmapCacheOnLoad, &bm);
    ID2D1RenderTarget *rt = nullptr;
    d2d->CreateWicBitmapRenderTarget(bm, D2D1::RenderTargetProperties(D2D1_RENDER_TARGET_TYPE_SOFTWARE,
                                         D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED), 96, 96), &rt);
    if (!rt) return 2;
    R.rt = rt;
    R.rt->CreateSolidColorBrush(INK, &R.br);
    R.rt->SetTextAntialiasMode(D2D1_TEXT_ANTIALIAS_MODE_GRAYSCALE);
    // sample data
    app.sb_found = app.sb_prepared = true;
    app.sb_program = L"C:\\Jogos\\Soulbrandt";
    app.rp_game = L"C:\\rpcs3\\games\\Demons Souls BLUS30443";
    app.rp_check = 1;
    app.art_ready = !g_artdir.empty();
    app.art_t = GetTickCount64() - 5000;
    app.hero = hero;
    app.screen = S_HOME;
    if (scr == L"targets") { app.screen = S_TARGETS; }
    else if (scr == L"rpcs3") app.screen = S_RPCS3;
    else if (scr == L"rpcs3bad") { app.screen = S_RPCS3; app.rp_check = -1; app.rp_game = L"C:\\Users\\Jogador\\Downloads";
        app.rp_msg = L"Esta pasta não parece ser a do Demon's Souls. Escolha a pasta do jogo, a PS3_GAME ou a USRDIR."; }
    else if (scr == L"installing") { app.screen = S_INSTALLING; app.step = "loading"; app.loading_n = 7; app.pct = 62;
        app.t_start = GetTickCount64() - 20000; app.font = L"novas"; }
    else if (scr == L"installed") { app.screen = S_INSTALLED; app.sb_installed = true; app.sb_subs = true; app.sb_fonts = L"hd"; app.done_fresh = true; }
    else if (scr == L"installed-rpcs3") { app.screen = S_INSTALLED; app.target_rpcs3 = true; app.rp_installed = true; app.rp_fonts = L"original"; }
    else if (scr == L"confirm") { app.screen = S_INSTALLED; app.sb_installed = true; app.sb_fonts = L"hd"; app.modal = M_CONFIRM;
        app.focus = ID_M_CANCEL; app.kb_focus = true; }
    else if (scr == L"about") app.modal = M_ABOUT;
    else if (scr == L"uninstalled") app.screen = S_UNINSTALLED;
    else if (scr == L"nosubs") { app.screen = S_INSTALLED; app.sb_installed = true; app.sb_fonts = L"hd"; app.sb_subs = false; }
    else if (scr == L"error") { app.screen = S_ERROR; app.err_code = L"running"; app.err_title = L"O Soulbrandt está aberto";
        app.err_msg = L"O Soulbrandt está aberto. Feche o jogo e tente de novo."; }
    else if (scr == L"notfound") { app.screen = S_NOTFOUND; app.art_ready = false; }
    else if (scr == L"samefont") { app.screen = S_FONTCHANGE; app.sb_installed = true; app.sb_fonts = L"novas"; app.font = L"novas";
        app.modal = M_SAMEFONT; app.focus = ID_M_CANCEL; app.kb_focus = true; }
    else if (scr == L"fontchange") { app.screen = S_FONTCHANGE; app.sb_installed = true; app.font = L"novas"; }
    rt->BeginDraw();
    paint(GetTickCount64());
    HRESULT hr = rt->EndDraw();
    R.drop();
    if (FAILED(hr)) return 3;
    Com<IWICStream> st;
    Com<IWICBitmapEncoder> enc;
    Com<IWICBitmapFrameEncode> fr;
    wic->CreateStream(&st);
    st->InitializeFromFilename(out.c_str(), GENERIC_WRITE);
    wic->CreateEncoder(GUID_ContainerFormatPng, nullptr, &enc);
    enc->Initialize(st, WICBitmapEncoderNoCache);
    enc->CreateNewFrame(&fr, nullptr);
    fr->Initialize(nullptr);
    fr->SetSize(SW_, SH_);
    WICPixelFormatGUID pf = GUID_WICPixelFormat32bppPBGRA;
    fr->SetPixelFormat(&pf);
    fr->WriteSource(bm, nullptr);
    fr->Commit();
    enc->Commit();
    return 0;
}

// ---------------------------------------------------------------------------------------------------------- main
int WINAPI wWinMain(HINSTANCE inst, HINSTANCE, PWSTR, int show) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    wchar_t exe[MAX_PATH];
    GetModuleFileNameW(nullptr, exe, MAX_PATH);
    g_dir = exe;
    g_dir = g_dir.substr(0, g_dir.find_last_of(L"\\/"));
    g_artdir = path(L"cache\\art");
    init_factories();

    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::wstring snap, scr = L"home", art;
    int hero = 0;
    for (int i = 1; i < argc; i++) {
        std::wstring a = argv[i];
        if (a == L"--snapshot" && i + 1 < argc) snap = argv[++i];
        else if (a == L"--screen" && i + 1 < argc) scr = argv[++i];
        else if (a == L"--art" && i + 1 < argc) art = argv[++i];
        else if (a == L"--hero" && i + 1 < argc) hero = _wtoi(argv[++i]);
    }
    if (!snap.empty()) {
        g_artdir = art;
        return snapshot(snap, scr, hero);
    }

    HANDLE single = CreateMutexW(nullptr, TRUE, L"DemonsSoulsPTBR.Launcher");
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        HWND other = FindWindowW(L"DeSPTBRLauncher", nullptr);
        if (other) { ShowWindow(other, SW_RESTORE); SetForegroundWindow(other); }
        return 0;
    }
    if (!exists(path(L"python\\python.exe")) || !exists(path(L"pack\\tools\\launcher_backend.py"))) {
        MessageBoxW(nullptr, L"Faltam arquivos do pacote ao lado deste programa (as pastas python e pack). "
                             L"Extraia o zip inteiro de novo e abra o PT-BR.exe de dentro da pasta PT-BR.",
                    L"Tradução PT-BR", MB_OK | MB_ICONWARNING);
        return 1;
    }
    BOOL anim = TRUE;
    SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, &anim, 0);
    app.reduced_motion = !anim;
    load_prefs();

    WNDCLASSEXW wc{sizeof(wc)};
    wc.style = CS_DROPSHADOW;
    wc.lpfnWndProc = wndproc;
    wc.hInstance = inst;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(1));
    wc.lpszClassName = L"DeSPTBRLauncher";
    RegisterClassExW(&wc);
    POINT pt;
    GetCursorPos(&pt);
    HMONITOR mon = MonitorFromPoint(pt, MONITOR_DEFAULTTOPRIMARY);
    MONITORINFO mi{sizeof(mi)};
    GetMonitorInfoW(mon, &mi);
    UINT dpix = 96, dpiy = 96;
    typedef HRESULT(WINAPI * GDFM)(HMONITOR, int, UINT *, UINT *);
    if (HMODULE sh = LoadLibraryW(L"shcore.dll")) {
        if (auto f = (GDFM)GetProcAddress(sh, "GetDpiForMonitor")) f(mon, 0, &dpix, &dpiy);
    }
    g_scale = dpix / 96.f;
    int w = (int)(WIN_W * g_scale), h = (int)(WIN_H * g_scale);
    int x = (mi.rcWork.left + mi.rcWork.right - w) / 2, y = (mi.rcWork.top + mi.rcWork.bottom - h) / 2;
    app.hwnd = CreateWindowExW(WS_EX_APPWINDOW, wc.lpszClassName, L"Tradução PT-BR · Demon's Souls",
                               WS_POPUP | WS_MINIMIZEBOX | WS_SYSMENU, x, y, w, h, nullptr, nullptr, inst, nullptr);
    int corner = 2;   // DWMWCP_ROUND (Windows 11; ignored elsewhere)
    DwmSetWindowAttribute(app.hwnd, 33, &corner, sizeof(corner));
    BOOL dark = TRUE;
    DwmSetWindowAttribute(app.hwnd, 20, &dark, sizeof(dark));
    ShowWindow(app.hwnd, show);
    UpdateWindow(app.hwnd);
    SetTimer(app.hwnd, 1, 33, nullptr);
    refresh_state();

    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    R.drop();
    if (single) CloseHandle(single);
    return 0;
}
