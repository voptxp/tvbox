# -*- coding: utf-8 -*-
# 91porna.com TVBox 采集爬虫
#
# 站点结构：
#   91视频    /comic/index/video?category=X        (详情 /comic/index/detail?video_key=NUM)
#   91短视频  /melonshort/{slug}                   (详情 /melonshort/video/{id}, 播放 /melonshort/embed/{id})
#   日本AV    /comic/index/av  /comic/av/relvideo  (详情 /comic/index/avdetail?video_key=XXX)
#   黑料吃瓜  /黑料吃瓜/{推荐|最新}                (纯图文文章，无视频)
#   AI成人    /comic/index/search?keyword=...      (与91视频同构)
#   91动漫    /comic/index/search?keyword=...      (与91视频同构)
#   精选合集  /moviesets[/{type}]                   (合集 -> 视频列表)
#
# 播放链路（comic 视频/AV）：
#   详情页 og:video -> /comic/index/embed?id=NUM
#   embed 页 packer JS -> /index/embed_play.js?img=..&u=..&t=..
#   embed_play.js packer JS -> 明文 m3u8（带 auth_key，有时效）
# 全部用字符串解析 + 内置 json，不依赖 lxml/pyquery。
import json
import re
import sys
import time
import requests
from html import unescape
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


def _search(kw):
    return '/comic/index/search?keyword=' + quote(kw, safe='')


def _hei(path):
    return '/' + quote(path, safe='/')


class Spider(Spider):

    host = 'https://91porna.com'

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://91porna.com/',
    }

    CATEGORIES = [
        # 91视频
        ('91视频·正在播放', '/comic/index/video?category=play'),
        ('91视频·热门排行', '/comic/index/video?category=now_month_hot'),
        ('91视频·国产原创', '/comic/index/video?category=original'),
        ('91视频·当前最热', '/comic/index/video?category=now_hot'),
        ('91视频·最近更新', '/comic/index/video?category=new_update'),
        ('91视频·10分钟以上', '/comic/index/video?category=ten_minutes'),
        ('91视频·20分钟以上', '/comic/index/video?category=twenty_minutes'),
        ('91视频·本月收藏', '/comic/index/video?category=now_month_collect'),
        ('91视频·高清', '/comic/index/video?category=hd'),
        ('91视频·每月最热', '/comic/index/video?category=month_hot'),
        ('91视频·本月讨论', '/comic/index/video?category=now_month_comment'),
        ('91视频·收藏最多', '/comic/index/video?category=max_collect'),
        ('91视频·吃瓜爆料', _search('吃瓜 黑料 爆料')),
        ('91视频·熟女做爱', _search('熟女')),
        # 91短视频
        ('短视频·素人自拍', '/melonshort/amateur'),
        ('短视频·原创自拍', '/melonshort/zipai'),
        ('短视频·高燃混剪', '/melonshort/hunjian'),
        ('短视频·反差系列', '/melonshort/fancha'),
        ('短视频·网红达人', '/melonshort/wanghong'),
        ('短视频·明星大瓜', '/melonshort/mingxing'),
        # 黑料吃瓜
        ('黑料吃瓜·推荐', _hei('黑料吃瓜/推荐')),
        ('黑料吃瓜·最新', _hei('黑料吃瓜/最新')),
        ('黑料吃瓜·今日吃瓜', _hei('黑料吃瓜/今日吃瓜/最新')),
        ('黑料吃瓜·学生校园', _hei('黑料吃瓜/学生校园/推荐')),
        ('黑料吃瓜·明星黑料', _hei('黑料吃瓜/明星黑料/推荐')),
        ('黑料吃瓜·网红黑料', _hei('黑料吃瓜/网红黑料/推荐')),
        ('黑料吃瓜·每日大赛', _hei('黑料吃瓜/每日大赛/推荐')),
        ('黑料吃瓜·名人合集', _hei('黑料吃瓜/名人合集/推荐')),
        ('黑料吃瓜·必看大瓜', _hei('黑料吃瓜/必看大瓜/推荐')),
        ('黑料吃瓜·吃瓜新闻', _hei('黑料吃瓜/吃瓜新闻/推荐')),
        ('黑料吃瓜·反差原创', _hei('黑料吃瓜/反差原创/推荐')),
        # AI成人
        ('AI成人', _search('ai成人')),
        ('AI成人短剧', _search('ai短剧')),
        ('AI漫剧', _search('ai漫剧')),
        ('AI美女', _search('ai美女')),
        ('AI换脸', _search('ai换脸')),
        # 日本AV
        ('日本AV', '/comic/index/av'),
        ('日本AV·多P群交', '/comic/av/relvideo?model=1&type=theme&order=week'),
        ('日本AV·无码解放', '/comic/av/relvideo?model=12&type=theme&order=week'),
        ('日本AV·中文字幕', '/comic/av/relvideo?model=5&type=theme&order=week'),
        ('日本AV·制服诱惑', '/comic/av/relvideo?model=6&type=theme&order=week'),
        ('日本AV·黑人专区', '/comic/av/relvideo?model=107&type=tag&order=week'),
        ('日本AV·SM调教', '/comic/av/relvideo?model=7&type=theme&order=week'),
        # 91动漫
        ('91动漫', _search('h动漫')),
        ('日本动漫', _search('日本动漫')),
        ('国产动漫', _search('国产动漫')),
        ('3D动漫', _search('3d动漫')),
        ('同人动漫', _search('同人动漫')),
        # 精选合集
        ('精选合集·最新', '/moviesets'),
        ('精选合集·排行榜', '/moviesets/rank'),
        ('精选合集·分类', '/moviesets/category'),
        ('精选合集·人物', '/moviesets/people'),
        ('精选合集·品牌', '/moviesets/brand'),
    ]

    def init(self, extend=''):
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ------------------------------------------------------------------ 网络层
    def _get(self, path, referer=None):
        url = path if path.startswith('http') else f'{self.host}{path}'
        h = {'referer': referer} if referer else {}
        r = self._session.get(url, headers=h, timeout=20)
        r.encoding = 'utf-8'
        return r.text

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        classes = [{'type_name': name, 'type_id': url} for name, url in self.CATEGORIES]
        raw = self._get('/')
        return {'class': classes, 'list': self._getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        url = self._page_url((tid or '').strip(), pg)
        raw = self._get(url)
        lst = self._getlist(raw)
        pc = self._pagecount(raw, tid)
        return {
            'list': lst,
            'page': pg,
            'pagecount': pc,
            'limit': len(lst),
            'total': pc * len(lst) if lst else 0,
        }

    def _page_url(self, url, pg):
        if pg <= 1:
            return url
        if not url:
            return '/'
        u = url.rstrip('/')
        if '/melonshort' in u or '/moviesets' in u:
            return f'{u}/{pg}'
        sep = '&' if '?' in u else '?'
        return f'{u}{sep}page={pg}'

    def _pagecount(self, raw, tid):
        m = re.search(r'total="(\d+)"', raw)
        if m:
            total = int(m.group(1))
            if not total:
                return 9999
            if '/melonshort' in (tid or ''):
                return total
            per = len(self._getlist(raw)) or 1
            return (total + per - 1) // per
        if 'rel="next"' in raw or 'page=' in raw:
            return 9999
        return 1

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid)

        if '/moviesets/' in vid and not re.search(r'/moviesets/(?:people|brand|category|rank)/[^/]+', vid):
            # 合集列表页：把每个合集当一部“影片”，点击后进入其视频列表
            lst = self._getlist(raw)
            return {'list': lst}

        if '/heiliao-chigua/' in vid:
            return {'list': [self._parse_heiliao(vid, raw)]}

        if '/melonshort/video/' in vid:
            return {'list': [self._parse_short(vid, raw)]}

        if re.search(r'/comic/index/(?:detail|avdetail)\?video_key=', vid):
            return {'list': [self._parse_comic(vid, raw)]}

        # 合集详情页：/moviesets/people|brand|category/{slug} -> 视频列表作为多集
        if '/moviesets/' in vid:
            return {'list': [self._parse_movieset(vid, raw)]}

        # 默认按 comic 处理
        return {'list': [self._parse_comic(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        url = _search((key or '').strip())
        if pg > 1:
            url += f'&page={pg}'
        try:
            raw = self._get(url)
            return {'list': self._getlist(raw)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        if '.m3u8' in url:
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        if '/melonshort/video/' in url:
            m = re.search(r'/melonshort/video/(\d+)', url)
            m3u8 = self._short_m3u8(m.group(1)) if m else ''
            if m3u8:
                return {'parse': 0, 'jx': 0, 'url': m3u8, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        if re.search(r'/comic/index/(?:detail|avdetail)\?video_key=', url):
            m3u8 = self._comic_m3u8(url)
            if m3u8:
                return {'parse': 0, 'jx': 0, 'url': m3u8, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 列表解析
    def _getlist(self, html):
        items = self._jsonld_items(html)
        named = [x for x in items if x.get('name')]
        if named:
            out = []
            seen = set()
            for it in named:
                url = it.get('url') or ''
                if not url or url in seen:
                    continue
                if not self._is_content_url(url):
                    continue
                seen.add(url)
                remark = (it.get('remarks') or '').strip()
                if len(remark) > 10:
                    remark = remark[:10]
                out.append({
                    'vod_id': url,
                    'vod_name': it.get('name') or '',
                    'vod_pic': it.get('pic') or '',
                    'vod_remarks': remark,
                })
            if out:
                return out
        return self._getlist_html(html)

    def _is_content_url(self, url):
        return any(k in url for k in (
            '/comic/index/detail?video_key=',
            '/comic/index/avdetail?video_key=',
            '/melonshort/video/',
            '/heiliao-chigua/',
            '/moviesets/',
        ))

    def _jsonld_items(self, html):
        items = []
        for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            data = m.group(1).strip()
            if 'ItemList' not in data:
                continue
            try:
                obj = json.loads(data)
            except Exception:
                continue
            found = self._walk_itemlist(obj)
            if found:
                items.extend(found)
        return items

    def _walk_itemlist(self, node):
        if isinstance(node, dict):
            if node.get('@type') == 'ItemList':
                out = []
                for it in node.get('itemListElement', []):
                    if not isinstance(it, dict):
                        continue
                    item = it.get('item') if isinstance(it.get('item'), dict) else {}
                    url = it.get('url') or item.get('url') or item.get('@id') or ''
                    name = item.get('name') or it.get('name') or ''
                    pic = ''
                    p = item.get('primaryImageOfPage')
                    if isinstance(p, dict):
                        pic = p.get('url') or ''
                    if not pic:
                        th = item.get('thumbnailUrl')
                        if isinstance(th, str):
                            pic = th
                        elif isinstance(th, list) and th:
                            pic = th[0]
                    if not pic:
                        img = item.get('image')
                        if isinstance(img, str):
                            pic = img
                        elif isinstance(img, list) and img:
                            pic = img[0]
                        elif isinstance(img, dict):
                            pic = img.get('url') or ''
                    remark = item.get('datePublished') or item.get('uploadDate') or ''
                    out.append({'url': url, 'name': name, 'pic': pic, 'remarks': remark})
                return out
            for v in node.values():
                r = self._walk_itemlist(v)
                if r:
                    return r
        elif isinstance(node, list):
            for v in node:
                r = self._walk_itemlist(v)
                if r:
                    return r
        return None

    def _getlist_html(self, html):
        out = []
        seen = set()
        anchors = []
        # 搜索结果卡片（带 data-click_position）
        for m in re.finditer(r'<a[^>]+href="(/comic/index/detail\?video_key=\d+)"[^>]*>(.*?)</a>', html, re.S):
            opening = m.group(0).split('>')[0]
            if 'data-click_position' in opening:
                anchors.append((m.group(1), m.group(2)))
        if not anchors:
            for m in re.finditer(r'<a[^>]+href="(/heiliao-chigua/\d+)"[^>]*>(.*?)</a>', html, re.S):
                opening = m.group(0).split('>')[0]
                if 'checkNum' in opening:
                    anchors.append((m.group(1), m.group(2)))
        for url, block in anchors:
            if url in seen:
                continue
            seen.add(url)
            title = ''
            mm = re.search(r'<img[^>]+alt="([^"]+)"', block)
            if mm:
                title = unescape(mm.group(1)).strip()
            if not title:
                mm = re.search(r'<h[12][^>]*>(.*?)</h[12]>', block, re.S)
                if mm:
                    title = unescape(re.sub(r'<[^>]+>', '', mm.group(1))).strip()
            pic = ''
            mm = re.search(r'data-src="([^"]+)"', block)
            if not mm:
                mm = re.search(r'<img[^>]+src="([^"]+)"', block)
            if mm:
                pic = mm.group(1)
            if not title:
                title = '黑料'
            out.append({'vod_id': self.host + url, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': ''})
        return out

    # ------------------------------------------------------------------ 详情解析
    def _video_object(self, html):
        for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            data = m.group(1).strip()
            if 'VideoObject' not in data:
                continue
            try:
                obj = json.loads(data)
            except Exception:
                continue
            vo = self._find_videoobject(obj)
            if vo:
                return vo
        return {}

    def _find_videoobject(self, node):
        if isinstance(node, dict):
            if node.get('@type') == 'VideoObject':
                pic = ''
                th = node.get('thumbnailUrl')
                if isinstance(th, str):
                    pic = th
                elif isinstance(th, list) and th:
                    pic = th[0]
                return {
                    'name': node.get('name') or '',
                    'desc': node.get('description') or '',
                    'pic': pic,
                    'embed': node.get('embedUrl') or '',
                    'date': node.get('uploadDate') or node.get('datePublished') or '',
                }
            for v in node.values():
                r = self._find_videoobject(v)
                if r:
                    return r
        elif isinstance(node, list):
            for v in node:
                r = self._find_videoobject(v)
                if r:
                    return r
        return None

    def _meta_content(self, raw, key):
        i = raw.find(key)
        if i < 0:
            return ''
        i = raw.find('content="', i)
        if i < 0:
            return ''
        i += len('content="')
        j = raw.find('"', i)
        if j < 0:
            return ''
        return unescape(raw[i:j]).strip()

    def _title(self, raw):
        m = re.search(r'<title>(.*?)</title>', raw, re.S)
        if m:
            return unescape(m.group(1)).strip()
        return ''

    def _clean_title(self, t):
        t = (t or '').strip()
        for sep in (' - 91', ' | 91', ' _ 91', ' - 黑料吃瓜'):
            i = t.find(sep)
            if i > 0:
                t = t[:i].strip()
        return t

    def _quality_label(self, m3u8):
        return 'H265' if '/m3m/' in m3u8 else '高清'

    def _parse_comic(self, vid, raw):
        vo = self._video_object(raw)
        name = vo.get('name') or self._meta_content(raw, 'property="og:title"') or self._title(raw)
        desc = vo.get('desc') or self._meta_content(raw, 'property="og:description"') or name
        pic = vo.get('pic') or self._meta_content(raw, 'property="og:image"')
        rel = (vo.get('date') or '')[:10]
        m3u8 = self._comic_m3u8(vid, raw)
        play_from = ''
        play_url = ''
        if m3u8:
            play_from = '在线'
            play_url = self._quality_label(m3u8) + chr(36) + m3u8
        return {
            'vod_id': vid,
            'vod_name': self._clean_title(name) or vid,
            'vod_pic': pic,
            'vod_content': desc or name,
            'vod_remarks': rel,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _parse_short(self, vid, raw):
        vo = self._video_object(raw)
        name = vo.get('name') or self._meta_content(raw, 'property="og:title"') or self._title(raw)
        desc = vo.get('desc') or self._meta_content(raw, 'property="og:description"') or name
        pic = vo.get('pic') or self._meta_content(raw, 'property="og:image"')
        rel = (vo.get('date') or '')[:10]
        m = re.search(r'/melonshort/video/(\d+)', vid)
        m3u8 = self._short_m3u8(m.group(1)) if m else ''
        play_from = ''
        play_url = ''
        if m3u8:
            play_from = '在线'
            play_url = self._quality_label(m3u8) + chr(36) + m3u8
        return {
            'vod_id': vid,
            'vod_name': self._clean_title(name) or vid,
            'vod_pic': pic,
            'vod_content': desc or name,
            'vod_remarks': rel,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _parse_movieset(self, vid, raw):
        name = self._meta_content(raw, 'property="og:title"') or self._title(raw)
        desc = self._meta_content(raw, 'property="og:description"') or name
        pic = self._meta_content(raw, 'property="og:image"')

        episodes = []
        seen = set()

        def collect(page_raw):
            added = 0
            for it in self._getlist(page_raw):
                uid = it.get('vod_id')
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                episodes.append((it.get('vod_name') or '视频') + chr(36) + uid)
                added += 1
            return added

        collect(raw)
        pc = self._pagecount(raw, vid)
        base = vid.rstrip('/')
        # 已知页数就翻到最后一页；未知页数(9999)则翻到空页为止，最多 100 页
        max_pg = pc if pc and pc != 9999 else 100
        for pg in range(2, max_pg + 1):
            try:
                page_raw = self._get(f'{base}/{pg}')
            except Exception:
                break
            if not collect(page_raw):
                break

        play_from = ''
        play_url = ''
        if episodes:
            play_from = '在线'
            play_url = '#'.join(episodes)
        return {
            'vod_id': vid,
            'vod_name': self._clean_title(name) or vid,
            'vod_pic': pic,
            'vod_content': desc or name,
            'vod_remarks': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _parse_heiliao(self, vid, raw):
        name = self._clean_title(self._meta_content(raw, 'property="og:title"') or self._title(raw))
        desc = self._meta_content(raw, 'property="og:description"') or name
        pic = self._meta_content(raw, 'property="og:image"')
        m3u8s = self._heiliao_m3u8(raw)
        play_from = ''
        play_url = ''
        if m3u8s:
            play_from = '在线'
            eps = []
            for i, u in enumerate(m3u8s):
                label = self._quality_label(u) if len(m3u8s) == 1 else ('视频%d' % (i + 1))
                eps.append(label + chr(36) + u)
            play_url = '#'.join(eps)
        return {
            'vod_id': vid,
            'vod_name': name or vid,
            'vod_pic': pic,
            'vod_content': desc or name,
            'vod_remarks': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _heiliao_m3u8(self, raw):
        out = []
        seen = set()
        for decoded in self._unpack_all(raw):
            m = re.search(r'encodeURIComponent\("([0-9a-f]{60,})"\)', decoded)
            if not m:
                continue
            u = m.group(1)
            t = int(time.time() / 2100)
            try:
                pj = self._get(f'/index/melon_detail_play.js?img=&u={u}&t={t}')
            except Exception:
                continue
            dec = self._unpack(pj)
            if not dec:
                dec = pj
            for u2 in re.findall(r'https?://[^"\'<>\\\s]+\.m3u8[^"\'<>\\\s]*', dec):
                u2 = unescape(u2).rstrip('\\')
                if u2 and u2 not in seen:
                    seen.add(u2)
                    out.append(u2)
        return out

    # ------------------------------------------------------------------ 播放解析
    def _comic_m3u8(self, detail_url, raw=None):
        if raw is None:
            raw = self._get(detail_url)
        embed = self._meta_content(raw, 'property="og:video"') or ''
        if not embed:
            vo = self._video_object(raw)
            embed = vo.get('embed') or ''
        if not embed or 'embed' not in embed:
            return ''
        try:
            eraw = self._get(embed, referer=detail_url)
        except Exception:
            return ''
        decoded = self._unpack(eraw)
        if not decoded:
            decoded = eraw
        m = re.search(r'img=([^&"\']+)', decoded)
        img = m.group(1) if m else ''
        m = re.search(r'encodeURIComponent\("([^"]+)"\)', decoded)
        u = m.group(1) if m else ''
        if not u:
            return ''
        t = int(time.time() / 2100)
        try:
            pj = self._get(f'/index/embed_play.js?img={img}&u={u}&t={t}', referer=embed)
        except Exception:
            return ''
        dec = self._unpack(pj)
        if not dec:
            dec = pj
        m3u8s = re.findall(r'https?://[^"\'<>\\\s]+\.m3u8[^"\'<>\\\s]*', dec)
        if m3u8s:
            return unescape(m3u8s[0]).rstrip('\\')
        return ''

    def _short_m3u8(self, sid):
        try:
            eraw = self._get(f'/melonshort/embed/{sid}')
        except Exception:
            return ''
        m3u8s = re.findall(r'https?://[^"\'<>\\\s]+\.m3u8[^"\'<>\\\s]*', eraw)
        if m3u8s:
            return unescape(m3u8s[0]).rstrip('\\')
        return ''

    # ------------------------------------------------------------------ packer 解码
    def _unpack(self, text):
        m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{.*?split\('\|'\),\s*0\s*,\s*\{\}\)\)", text, re.S)
        if not m:
            return ''
        return self._decode_packer(m.group(0))

    def _unpack_all(self, text):
        out = []
        for m in re.finditer(r"eval\(function\(p,a,c,k,e,d\)\{.*?split\('\|'\),\s*0\s*,\s*\{\}\)\)", text, re.S):
            d = self._decode_packer(m.group(0))
            if d:
                out.append(d)
        return out

    def _decode_packer(self, code):
        m2 = re.search(r"\}\('(.*)',(\d+),(\d+),'(.*)'\.split\('\|'\),\s*0\s*,\s*\{\}\)", code, re.DOTALL)
        if not m2:
            return ''
        p, a, c, k = m2.group(1), int(m2.group(2)), int(m2.group(3)), m2.group(4).split('|')
        d = {}
        for i in range(c - 1, -1, -1):
            key = self._packer_key(i, a)
            d[key] = k[i] if i < len(k) and k[i] else key
        return re.sub(r'[A-Za-z0-9_]+', lambda mm: d.get(mm.group(0), mm.group(0)), p)

    def _packer_key(self, c, a):
        def digit(x):
            if x < 10:
                return chr(48 + x)
            if x <= 35:
                return chr(87 + x)
            return chr(x + 29)
        s = ''
        while True:
            rem = c % a
            s = digit(rem) + s
            c //= a
            if c <= 0:
                break
        return s
