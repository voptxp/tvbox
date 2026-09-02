# -*- coding: utf-8 -*-
# nJAV (njavtv.com) TVBox 采集爬虫
#
# 该站有 Cloudflare TLS/JA3 指纹检测，TVBox 内 requests 会被 403，
# 因此所有请求都走本地 Go tls-client 代理：
#   http://192.168.0.3:12316/?url=<目标URL>&referer=<Referer>
#
# 结构：
#   列表  /dm{编号}            （如 /dm339）
#   详情  /{dvd_id}            （如 /dldss-531）
#   播放  surrit.com 的 m3u8（详情页 packer 混淆 JS 解码得到）
import base64
import re
import sys
from html import unescape
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://njavtv.com'
    proxy = 'http://192.168.0.3:12316/'

    CATEGORIES = [
        ('nJAV', 'dm339'),
    ]

    def init(self, extend=''):
        self._proxy = self.proxy
        if extend:
            try:
                import json
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if cfg.get('proxy'):
                    self._proxy = cfg['proxy'].rstrip('/') + '/'
                if cfg.get('dm'):
                    self.CATEGORIES = [('nJAV', str(cfg['dm']))]
            except Exception:
                pass

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ------------------------------------------------------------------ 网络层（走 Go 代理）
    def _get(self, url, referer=''):
        import requests
        if not url.startswith('http'):
            url = self.host + url
        q = '?url=' + quote(url, safe='')
        if referer:
            q += '&referer=' + quote(referer, safe='')
        r = requests.get(self._proxy + q, timeout=30)
        r.encoding = 'utf-8'
        return r.text

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        classes = [{'type_name': name, 'type_id': tid} for name, tid in self.CATEGORIES]
        raw = self._get(self.host + '/')
        return {'class': classes, 'list': self._getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = (tid or 'dm339').strip().strip('/')
        url = f'{self.host}/{tid}'
        raw = self._get(url, referer=self.host + '/')
        return {
            'list': self._getlist(raw),
            'page': pg,
            'pagecount': 1,
            'limit': len(self._getlist(raw)),
            'total': len(self._getlist(raw)),
        }

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid, referer=self.host + '/')
        return {'list': [self._parse_detail(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        kw = quote((key or '').strip(), safe='')
        raw = self._get(f'{self.host}/search/{kw}', referer=self.host + '/')
        return {'list': self._getlist(raw)}

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self._ua()}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def _ua(self):
        return ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # ------------------------------------------------------------------ 解析
    def _getlist(self, html):
        out, seen = [], set()
        for m in re.finditer(r'<a[^>]*href="https://njavtv\.com/([a-z0-9-]+)"[^>]*>\s*([^<]{5,})\s*</a>', html):
            dvd_id = m.group(1)
            title = unescape(m.group(2)).strip()
            if dvd_id in seen or not title:
                continue
            if not re.search(r'\d', dvd_id):
                continue
            seen.add(dvd_id)
            out.append({
                'vod_id': f'{self.host}/{dvd_id}',
                'vod_name': title,
                'vod_pic': f'https://fourhoi.com/{dvd_id}/cover-n.jpg',
                'vod_remarks': '',
            })
        return out

    def _parse_detail(self, vid, html):
        mm = re.search(r'<title>(.*?)</title>', html, re.S)
        name = unescape(mm.group(1)).strip() if mm else vid
        name = re.sub(r'\s*-\s*nJAV\s*$', '', name).strip()

        m3u8 = self._extract_m3u8(html)
        pic = ''
        if m3u8:
            dvd_id = vid.rstrip('/').split('/')[-1]
            pic = f'https://fourhoi.com/{dvd_id}/cover-n.jpg'

        play_from = ''
        play_url = ''
        if m3u8:
            play_from = '在线'
            play_url = '高清' + chr(36) + self._proxy_m3u8(m3u8)

        return {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_content': name,
            'vod_remarks': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _extract_m3u8(self, html):
        dec = self._unpack(html)
        for u in re.findall(r'https?://[^\'\\"]+\.m3u8', dec):
            if '/1080p/' in u:
                return u
        for u in re.findall(r'https?://[^\'\\"]+\.m3u8', dec):
            if '/720p/' in u:
                return u
        for u in re.findall(r'https?://[^\'\\"]+\.m3u8', dec):
            return u
        return ''

    def _proxy_m3u8(self, m3u8):
        q = '?url=' + quote(m3u8, safe='')
        q += '&referer=' + quote(self.host + '/', safe='')
        return self._proxy + q

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
            key = self._key(i, a)
            d[key] = k[i] if i < len(k) and k[i] else key
        return re.sub(r'[A-Za-z0-9_]+', lambda mm: d.get(mm.group(0), mm.group(0)), p)

    def _key(self, c, a):
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
