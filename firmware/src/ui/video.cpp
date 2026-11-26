// MJPEG playback (PLAN.md §6, phase 6). Silent.
//
// Container (.mjpeg, written by tools/video.py):
//   0  "MJPG"            magic
//   4  u16 version (1)
//   6  u16 fps x 100
//   8  u16 width, 10 u16 height
//   12 u32 frame count
//   16 frames: u32 length + baseline JPEG bytes, repeated
//
// One clip plays at a time. Each frame is decoded with TJpgDec (bundled with
// LVGL) straight into one RGB565 frame buffer that an lv_image shows. A clip
// is limited to kMaxFrameBytes so the device build fits in memory without PSRAM.
#include <cstring>

#if __has_include("src/libs/tjpgd/tjpgd.h")
#include "src/libs/tjpgd/tjpgd.h"
#else
#include "libs/tjpgd/tjpgd.h"
#endif

#include "ui/platform.h"
#include "ui/ui.h"

namespace ui {
namespace detail {

constexpr size_t kMaxFrameBytes = 240 * 200 * 2;  // 96 000 bytes
constexpr size_t kWorkBytes = 4096;

namespace {

struct Clip {
    std::string src;
    bool autoplay = false, loop = true;
};

struct Player {
    lv_obj_t* img = nullptr;
    lv_fs_file_t file{};
    bool open = false;
    uint16_t w = 0, h = 0, fpsX100 = 1200;
    uint32_t frames = 0, index = 0;
    bool loop = true;
    uint8_t* fb = nullptr;
    std::vector<uint8_t> jpeg;
    size_t jpegPos = 0;
    uint8_t work[kWorkBytes];
    lv_image_dsc_t dsc{};
    lv_timer_t* timer = nullptr;
};

Player* g_player = nullptr;

void onVideoDelete(lv_event_t* e) {
    auto* c = static_cast<Clip*>(lv_event_get_user_data(e));
    if (g_player && g_player->img == lv_event_get_target(e)) videoStopAll();
    delete c;
}

uint16_t rd16(const uint8_t* p) { return static_cast<uint16_t>(p[0] | (p[1] << 8)); }
uint32_t rd32(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) | (static_cast<uint32_t>(p[2]) << 16) |
           (static_cast<uint32_t>(p[3]) << 24);
}

size_t jpegIn(JDEC* jd, uint8_t* buf, size_t n) {
    auto* p = static_cast<Player*>(jd->device);
    size_t left = p->jpeg.size() - p->jpegPos;
    if (n > left) n = left;
    if (buf) std::memcpy(buf, p->jpeg.data() + p->jpegPos, n);
    p->jpegPos += n;
    return n;
}

int jpegOut(JDEC* jd, void* bitmap, JRECT* r) {
    auto* p = static_cast<Player*>(jd->device);
    const uint8_t* src = static_cast<const uint8_t*>(bitmap);  // RGB888 (JD_FORMAT 0)
    for (int y = r->top; y <= r->bottom; ++y) {
        if (y >= p->h) break;
        uint16_t* row = reinterpret_cast<uint16_t*>(p->fb) + static_cast<size_t>(y) * p->w;
        for (int x = r->left; x <= r->right; ++x) {
            uint8_t R = *src++, G = *src++, B = *src++;
            if (x < p->w) row[x] = static_cast<uint16_t>(((R & 0xF8) << 8) | ((G & 0xFC) << 3) | (B >> 3));
        }
    }
    return 1;
}

bool readFrame(Player* p) {
    if (p->index >= p->frames) {
        if (!p->loop) return false;
        lv_fs_seek(&p->file, 16, LV_FS_SEEK_SET);
        p->index = 0;
    }
    uint8_t lenb[4];
    uint32_t got = 0;
    if (lv_fs_read(&p->file, lenb, 4, &got) != LV_FS_RES_OK || got != 4) return false;
    uint32_t len = rd32(lenb);
    if (len == 0 || len > 512 * 1024) return false;
    p->jpeg.resize(len);
    if (lv_fs_read(&p->file, p->jpeg.data(), len, &got) != LV_FS_RES_OK || got != len) return false;
    p->index++;
    p->jpegPos = 0;
    JDEC jd;
    if (jd_prepare(&jd, jpegIn, p->work, kWorkBytes, p) != JDR_OK) return false;
    if (jd.width != p->w || jd.height != p->h) return false;
    return jd_decomp(&jd, jpegOut, 0) == JDR_OK;
}

void tick(lv_timer_t*) {
    Player* p = g_player;
    if (!p) return;
    if (!readFrame(p)) {
        if (p->timer) lv_timer_pause(p->timer);
        return;
    }
    lv_image_set_src(p->img, &p->dsc);
    lv_obj_invalidate(p->img);
}

}  // namespace

void videoAttach(lv_obj_t* img, const std::string& lvSrc, bool autoplay, bool loop) {
    // The clip travels as the DELETE handler's user data; clipOf() finds it again.
    auto* c = new Clip{lvSrc, autoplay, loop};
    lv_obj_add_event_cb(img, onVideoDelete, LV_EVENT_DELETE, c);
    if (autoplay) {
        lv_obj_update_layout(img);
        videoPlay(img);
    }
}

static Clip* clipOf(lv_obj_t* img) {
    uint32_t n = lv_obj_get_event_count(img);
    for (uint32_t i = 0; i < n; ++i) {
        lv_event_dsc_t* d = lv_obj_get_event_dsc(img, i);
        if (lv_event_dsc_get_cb(d) == onVideoDelete) return static_cast<Clip*>(lv_event_dsc_get_user_data(d));
    }
    return nullptr;
}

void videoPlay(lv_obj_t* img) {
    Clip* c = clipOf(img);
    if (!c) return;
    videoStopAll();
    auto* p = new Player();
    p->img = img;
    p->loop = c->loop;
    if (lv_fs_open(&p->file, c->src.c_str(), LV_FS_MODE_RD) != LV_FS_RES_OK) {
        platform().log("video not found: " + c->src);
        delete p;
        return;
    }
    p->open = true;
    uint8_t hdr[16];
    uint32_t got = 0;
    if (lv_fs_read(&p->file, hdr, 16, &got) != LV_FS_RES_OK || got != 16 || std::memcmp(hdr, "MJPG", 4) != 0) {
        platform().log("not an MJPG clip: " + c->src);
        lv_fs_close(&p->file);
        delete p;
        return;
    }
    p->fpsX100 = rd16(hdr + 6);
    p->w = rd16(hdr + 8);
    p->h = rd16(hdr + 10);
    p->frames = rd32(hdr + 12);
    size_t bytes = static_cast<size_t>(p->w) * p->h * 2;
    if (bytes == 0 || bytes > kMaxFrameBytes || p->fpsX100 == 0) {
        platform().log("clip too large for device memory: " + c->src);
        lv_fs_close(&p->file);
        delete p;
        return;
    }
    p->fb = static_cast<uint8_t*>(lv_malloc(bytes));
    if (!p->fb) {
        platform().log("out of memory for video frame");
        lv_fs_close(&p->file);
        delete p;
        return;
    }
    std::memset(p->fb, 0, bytes);
    p->dsc.header.magic = LV_IMAGE_HEADER_MAGIC;
    p->dsc.header.cf = LV_COLOR_FORMAT_RGB565;
    p->dsc.header.w = p->w;
    p->dsc.header.h = p->h;
    p->dsc.header.stride = p->w * 2;
    p->dsc.data = p->fb;
    p->dsc.data_size = bytes;
    g_player = p;
    tick(nullptr);  // first frame immediately
    p->timer = lv_timer_create(tick, 100000u / p->fpsX100, nullptr);
}

void videoStopAll() {
    Player* p = g_player;
    if (!p) return;
    g_player = nullptr;
    if (p->timer) lv_timer_delete(p->timer);
    if (p->open) lv_fs_close(&p->file);
    if (p->img && lv_obj_is_valid(p->img)) {
        lv_image_set_src(p->img, nullptr);
    }
    lv_free(p->fb);
    delete p;
}

}  // namespace detail
}  // namespace ui
