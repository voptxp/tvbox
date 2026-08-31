# -*- coding: utf-8 -*-
# KanAV (kanav.ad) TVBox 采集爬虫
#
# 结构：
#   分类   /index.php/vod/type/id/{tid}.html      分页 /index.php/vod/type/id/{tid}/page/{N}.html
#   热门   /index.php/label/hot.html
#   搜索   /index.php/vod/search.html?wd={kw}&by=type_id
#          分页 /index.php/vod/search/by/type_id/page/{N}/wd/{kw}.html
#   播放   /index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
#
# 播放页里 var player_aaaa={...} 的 url 字段是加密的：
#   encrypt=1 -> urlencode
#   encrypt=2 -> base64(urlencode(url))
# m3u8 需要 Referer: https://kanav.ad/
import base64
import json
import re
import sys
import requests
from html import unescape
from urllib.parse import quote, unquote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://kanav.ad'

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://kanav.ad/',
    }

    CATEGORIES = [
        ('中文字幕', '/index.php/vod/type/id/1.html'),
        ('日韩有码', '/index.php/vod/type/id/2.html'),
        ('日韩无码', '/index.php/vod/type/id/3.html'),
        ('国产AV', '/index.php/vod/type/id/4.html'),
        ('流出自拍', '/index.php/vod/type/id/22.html'),
        ('自拍泄密', '/index.php/vod/type/id/30.html'),
        ('探花约炮', '/index.php/vod/type/id/31.html'),
        ('主播录制', '/index.php/vod/type/id/32.html'),
        ('动漫番剧', '/index.php/vod/type/id/20.html'),
        ('里番', '/index.php/vod/type/id/25.html'),
        ('泡面番', '/index.php/vod/type/id/26.html'),
        ('Motion Anime', '/index.php/vod/type/id/27.html'),
        ('3D动画', '/index.php/vod/type/id/28.html'),
        ('同人作品', '/index.php/vod/type/id/29.html'),
        ('热门影片', '/index.php/label/hot.html'),
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
        pc = self._pagecount(raw)
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
        u = (url or '').rstrip('/')
        if u.endswith('.html'):
            u = u[:-5]
        return f'{u}/page/{pg}.html'

    def _pagecount(self, raw):
        nums = [int(x) for x in re.findall(r'/page/(\d+)', raw)]
        return max(nums) if nums else 1

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid)
        return {'list': [self._parse_play(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        if pg <= 1:
            url = f'/index.php/vod/search.html?wd={kw}&by=type_id'
        else:
            url = f'/index.php/vod/search/by/type_id/page/{pg}/wd/{kw}.html'
        try:
            raw = self._get(url)
            return {'list': self._getlist(raw)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        if '.m3u8' in url:
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        if '/vod/play/id/' in url:
            try:
                raw = self._get(url)
            except Exception:
                return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}
            m3u8 = self._extract_m3u8(raw)
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
        parts = html.split('<div class="video-item">')
        for part in parts[1:]:
            block = part
            lm = re.search(r'href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', block)
            if not lm:
                continue
            url = self.host + lm.group(1)
            if url in seen:
                continue
            seen.add(url)
            title = ''
            tm = re.search(r'<img[^>]*alt="([^"]*)"', block)
            if tm:
                title = unescape(tm.group(1)).strip()
            pic = ''
            pm = re.search(r'<img[^>]*(?:data-original|src)="(https?://[^"]+)"', block)
            if pm:
                pic = pm.group(1)
            if not title:
                title = '视频'
            out.append({'vod_id': url, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': ''})
        return out

    def _parse_play(self, vid, raw):
        data = {}
        i = raw.find('var player_aaaa=')
        if i >= 0:
            j = raw.find('</script>', i)
            if j >= 0:
                txt = raw[i + len('var player_aaaa='):j].strip().rstrip(';')
                try:
                    data = json.loads(txt)
                except Exception:
                    data = {}

        vd = data.get('vod_data') or {}
        name = vd.get('vod_name') or ''
        actor = vd.get('vod_actor') or ''
        director = vd.get('vod_director') or ''
        m3u8 = self._decode_url(data.get('url') or '', data.get('encrypt', 0))

        if not name:
            m = re.search(r'<title>(.*?)</title>', raw, re.S)
            if m:
                name = unescape(m.group(1)).strip()
                name = name.replace('在线播放 - ', '', 1).split(' - KanAV')[0].strip()

        pic = ''
        m = re.search(r'<img[^>]*class="countext-img"[^>]*src="([^"]+)"', raw)
        if m:
            pic = m.group(1)

        desc = ''
        if actor:
            desc = '演员: ' + actor
        if director:
            desc = (desc + '\n' if desc else '') + '导演: ' + director

        play_from = ''
        play_url = ''
        if m3u8:
            play_from = '在线'
            play_url = '高清' + chr(36) + m3u8

        return {
            'vod_id': vid,
            'vod_name': name or vid,
            'vod_pic': pic,
            'vod_content': desc or name,
            'vod_remarks': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _extract_m3u8(self, raw):
        i = raw.find('var player_aaaa=')
        if i < 0:
            return ''
        j = raw.find('</script>', i)
        if j < 0:
            return ''
        txt = raw[i + len('var player_aaaa='):j].strip().rstrip(';')
        try:
            data = json.loads(txt)
        except Exception:
            return ''
        return self._decode_url(data.get('url') or '', data.get('encrypt', 0))

    def _decode_url(self, url, encrypt):
        encrypt = int(encrypt or 0)
        if not url:
            return ''
        if encrypt == 1:
            return unquote(url)
        if encrypt == 2:
            try:
                return unquote(base64.b64decode(url).decode('utf-8', 'ignore'))
            except Exception:
                return unquote(url)
        return url
