// Minimal JSON reader for the back end's output (objects, arrays, strings, numbers, true/false/null).
#pragma once
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <string>
#include <vector>

struct JVal {
    enum Kind { Null, Bool, Num, Str, Arr, Obj } kind = Null;
    bool b = false;
    double n = 0;
    std::string s;                       // UTF-8
    std::vector<JVal> a;
    std::map<std::string, JVal> o;

    const JVal &operator[](const char *k) const {
        static const JVal none;
        auto it = o.find(k);
        return it == o.end() ? none : it->second;
    }
    bool truthy() const { return kind == Bool ? b : kind == Num ? n != 0 : kind == Str ? !s.empty() : kind != Null; }
    std::string str(const char *def = "") const { return kind == Str ? s : def; }
    int num(int def = 0) const { return kind == Num ? (int)n : def; }
};

class JParser {
public:
    explicit JParser(const std::string &t) : s(t) {}
    bool parse(JVal &out) { ws(); return value(out); }

private:
    const std::string &s;
    size_t i = 0;
    void ws() { while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n')) i++; }
    bool lit(const char *w) {
        size_t n = strlen(w);
        if (s.compare(i, n, w) == 0) { i += n; return true; }
        return false;
    }
    static void put_utf8(std::string &o, unsigned cp) {
        if (cp < 0x80) o += (char)cp;
        else if (cp < 0x800) { o += (char)(0xC0 | (cp >> 6)); o += (char)(0x80 | (cp & 63)); }
        else if (cp < 0x10000) { o += (char)(0xE0 | (cp >> 12)); o += (char)(0x80 | ((cp >> 6) & 63)); o += (char)(0x80 | (cp & 63)); }
        else { o += (char)(0xF0 | (cp >> 18)); o += (char)(0x80 | ((cp >> 12) & 63)); o += (char)(0x80 | ((cp >> 6) & 63)); o += (char)(0x80 | (cp & 63)); }
    }
    bool string(std::string &o) {
        if (s[i] != '"') return false;
        i++;
        while (i < s.size() && s[i] != '"') {
            char c = s[i++];
            if (c != '\\') { o += c; continue; }
            if (i >= s.size()) return false;
            char e = s[i++];
            switch (e) {
            case 'n': o += '\n'; break;
            case 't': o += '\t'; break;
            case 'r': o += '\r'; break;
            case 'b': o += '\b'; break;
            case 'f': o += '\f'; break;
            case 'u': {
                if (i + 4 > s.size()) return false;
                unsigned cp = (unsigned)strtoul(s.substr(i, 4).c_str(), nullptr, 16);
                i += 4;
                if (cp >= 0xD800 && cp < 0xDC00 && i + 6 <= s.size() && s[i] == '\\' && s[i + 1] == 'u') {
                    unsigned lo = (unsigned)strtoul(s.substr(i + 2, 4).c_str(), nullptr, 16);
                    i += 6;
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                }
                put_utf8(o, cp);
                break;
            }
            default: o += e;
            }
        }
        if (i >= s.size()) return false;
        i++;
        return true;
    }
    bool value(JVal &v) {
        if (i >= s.size()) return false;
        char c = s[i];
        if (c == '{') {
            v.kind = JVal::Obj; i++; ws();
            if (i < s.size() && s[i] == '}') { i++; return true; }
            for (;;) {
                ws();
                std::string k;
                if (!string(k)) return false;
                ws();
                if (i >= s.size() || s[i] != ':') return false;
                i++; ws();
                if (!value(v.o[k])) return false;
                ws();
                if (i < s.size() && s[i] == ',') { i++; continue; }
                if (i < s.size() && s[i] == '}') { i++; return true; }
                return false;
            }
        }
        if (c == '[') {
            v.kind = JVal::Arr; i++; ws();
            if (i < s.size() && s[i] == ']') { i++; return true; }
            for (;;) {
                ws();
                v.a.emplace_back();
                if (!value(v.a.back())) return false;
                ws();
                if (i < s.size() && s[i] == ',') { i++; continue; }
                if (i < s.size() && s[i] == ']') { i++; return true; }
                return false;
            }
        }
        if (c == '"') { v.kind = JVal::Str; return string(v.s); }
        if (lit("true")) { v.kind = JVal::Bool; v.b = true; return true; }
        if (lit("false")) { v.kind = JVal::Bool; v.b = false; return true; }
        if (lit("null")) { v.kind = JVal::Null; return true; }
        char *end = nullptr;
        v.n = strtod(s.c_str() + i, &end);
        if (end == s.c_str() + i) return false;
        v.kind = JVal::Num;
        i = end - s.c_str();
        return true;
    }
};

inline bool parse_json(const std::string &t, JVal &out) { JParser p(t); return p.parse(out); }
