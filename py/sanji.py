# -*- coding: utf-8 -*-
# 三级片 (91porna.com) 单类采集
# 数据源：https://91porna.com/comic/index/search?keyword=三级片
# 与 91porna 视频链路一致：详情页 og:video -> embed -> embed_play.js -> m3u8
import json
import re
import sys
import time
import requests
from html import unescape
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://91porna.com'

    KEYWORD = '三级片'
    SEARCH_PATH = '/comic/index/search?keyword=' + quote(KEYWORD, safe='')

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://91porna.com/',
    }

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
        raw = self._get(self.SEARCH_PATH)
        classes = [{'type_name': self.KEYWORD, 'type_id': self.SEARCH_PATH}]
        return {'class': classes, 'list': self._getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        url = (tid or '').strip() or self.SEARCH_PATH
        if pg > 1:
            url += '&page=' + str(pg)
        raw = self._get(url)
        lst = self._getlist(raw)
        pc = self._pagecount(raw)
        return {
            'list': lst,
            'page': pg,
            'pagecount': pc,
            'limit': len(lst),
            'total': pc * len(lst) if lst else 0,
        }

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid)
        return {'list': [self._parse_detail(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = (key or '').strip()
        url = '/comic/index/search?keyword=' + quote(kw, safe='') if kw else self.SEARCH_PATH
        if pg > 1:
            url += '&page=' + str(pg)
        try:
            raw = self._get(url)
            return {'list': self._getlist(raw)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        if '.m3u8' in url:
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        if '/comic/index/detail' in url or '/comic/index/avdetail' in url:
            m3u8 = self._comic_m3u8(url)
            if m3u8:
                return {'parse': 0, 'jx': 0, 'url': m3u8, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析
    def _getlist(self, html):
        out = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="(/comic/index/detail\?video_key=\d+)"[^>]*>(.*?)</a>', html, re.S):
            opening = m.group(0).split('>')[0]
            if 'data-click_position' not in opening:
                continue
            url = m.group(1)
            block = m.group(2)
            if url in seen:
                continue
            seen.add(url)
            title = ''
            mm = re.search(r'<img[^>]+alt="([^"]+)"', block)
            if mm:
                title = unescape(mm.group(1)).strip()
            pic = ''
            mm = re.search(r'data-src="([^"]+)"', block)
            if mm:
                pic = mm.group(1)
            if not title:
                title = '视频'
            out.append({'vod_id': self.host + url, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': ''})
        return out

    def _pagecount(self, raw):
        m = re.search(r'total="(\d+)"', raw)
        if m:
            total = int(m.group(1))
            if not total:
                return 9999
            per = len(self._getlist(raw)) or 1
            return (total + per - 1) // per
        if 'rel="next"' in raw or 'page=' in raw:
            return 9999
        return 1

    def _parse_detail(self, vid, raw):
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

    # ------------------------------------------------------------------ packer 解码
    def _unpack(self, text):
        m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{.*?split\('\|'\),\s*0\s*,\s*\{\}\)\)", text, re.S)
        if not m:
            return ''
        code = m.group(0)
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
