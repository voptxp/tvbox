/**
 * AV时间 (avtime.tv) 点播采集源
 * 适配 FongMi TVBox / TVBox 新版 JS 接口 (JS0 / Spider 6.x)
 *
 * 站点: https://avtime.tv/
 * 分类: 中文字幕(28) 国产(20) 日本有码(21) 日本无码(22) 欧美(23) 动漫(24) 伦理(25) 韩国(36) 另类(41)
 * 列表: /vodshow/{type}--------{page}---2/
 * 搜索: /vodsearch/{wd}----------{page}---/
 * 详情: /vodplay/{id}-1-1/
 * 播放: 从播放页 player_aaaa JSON 中提取直链 m3u8
 */

const host = 'https://avtime.tv';
const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": host + "/"
};

// 分类: [type_id, type_name]
const CLASSES = [
    ["28", "中文字幕"],
    ["20", "国产"],
    ["21", "日本有码"],
    ["22", "日本无码"],
    ["23", "欧美"],
    ["24", "动漫"],
    ["25", "伦理"],
    ["36", "韩国"],
    ["41", "另类"]
];

async function init(cfg) {}

const m = (s, r, i = 1) => (s.match(r) || [])[i] || "";
const strip = s => (s || "").replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();
const fixPic = p => (p && p.startsWith('/') ? host + p : p);

/**
 * 解析视频卡片列表
 * @param {string} html 页面 HTML
 * @param {string} selector 卡片选择器: 首页 a.card, 分类/搜索 a.card-item
 */
function getList(html, selector) {
    const seen = {};
    return pdfa(html, selector).map(it => {
        const id = m(it, /href="\/vodplay\/(\d+)-/);
        if (!id || seen[id]) return null;
        seen[id] = 1;
        const name = strip(m(it, /class="desc">([\s\S]*?)<\/div>/));
        if (!name) return null;
        return {
            vod_id: id,
            vod_name: name,
            vod_pic: fixPic(m(it, /data-src="([^"]+)"/) || m(it, /src="([^"]+)"/)),
            vod_remarks: strip(m(it, /class="read">([\s\S]*?)<\/div>/)) || strip(m(it, /class="read">([\s\S]*?)<\/li>/))
        };
    }).filter(Boolean);
}

/** 解析播放页 player_aaaa JSON */
function parsePlayer(h) {
    const raw = m(h, /var player_aaaa=(\{[\s\S]*?\})<\/script>/);
    if (!raw) return null;
    try {
        return JSON.parse(raw);
    } catch (e) {
        return null;
    }
}

/** 首页分类 */
async function home(filter) {
    return JSON.stringify({
        class: CLASSES.map(([type_id, type_name]) => ({ type_id, type_name })),
        filters: {}
    });
}

/** 首页推荐 */
async function homeVod() {
    const r = await req(host + '/', { headers });
    return JSON.stringify({ list: getList(r.content, 'a.card') });
}

/** 分类列表 */
async function category(tid, pg, filter, extend) {
    const p = parseInt(pg, 10) || 1;
    const r = await req(`${host}/vodshow/${tid}--------${p}---2/`, { headers });
    const h = r.content;
    const pc = parseInt(m(h, /data-total="(\d+)"/), 10) || 9999;
    return JSON.stringify({ page: p, pagecount: pc, limit: 24, list: getList(h, 'a.card-item') });
}

/** 详情 */
async function detail(id) {
    const r = await req(`${host}/vodplay/${id}-1-1/`, { headers });
    const h = r.content;
    const pj = parsePlayer(h);
    const name = (pj && pj.vod_data && pj.vod_data.vod_name)
        ? pj.vod_data.vod_name
        : strip(m(h, /class="tips-title">([\s\S]*?)<\/div>/));
    return JSON.stringify({
        list: [{
            vod_id: id,
            vod_name: name,
            vod_pic: fixPic(m(h, /data-pic="([^"]+)"/)),
            vod_actor: pj && pj.vod_data ? (pj.vod_data.vod_actor || '') : '',
            vod_director: pj && pj.vod_data ? (pj.vod_data.vod_director || '') : '',
            vod_class: pj && pj.vod_data ? (pj.vod_data.vod_class || '') : '',
            vod_content: name,
            vod_play_from: '在线播放',
            vod_play_url: '在线播放$' + `/vodplay/${id}-1-1/`
        }]
    });
}

/** 搜索 */
async function search(wd, quick, pg) {
    const p = parseInt(pg, 10) || 1;
    const r = await req(`${host}/vodsearch/${encodeURIComponent(wd)}----------${p}---/`, { headers });
    const h = r.content;
    const pc = parseInt(m(h, /data-total="(\d+)"/), 10) || 1;
    return JSON.stringify({ page: p, pagecount: pc, list: getList(h, 'a.card-item') });
}

/** 播放解析 */
async function play(flag, id, flags) {
    const url = /^https?:/.test(id) ? id : host + id;
    const r = await req(url, { headers });
    const pj = parsePlayer(r.content);
    if (pj && pj.url) {
        return JSON.stringify({ parse: 0, url: pj.url.replace(/\\/g, ''), header: headers });
    }
    return JSON.stringify({ parse: 1, url, header: headers });
}

export default { init, home, homeVod, category, detail, search, play };
