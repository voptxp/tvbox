# -*- coding: utf-8 -*-
# 91md.me (麻豆视频) TVBox 采集爬虫（maccms）
#
# 分类：/index.php/vod/type/id/{tid}.html      分页 /index.php/vod/type/id/{tid}/page/{N}.html
# 播放：/index.php/vod/play/id/{vid}/sid/1/nid/1.html
# 播放地址：播放页 var player_aaaa={...} 的 url 字段（encrypt=0 明文）
# 海报：由 m3u8 地址推导（同目录 vod.jpg）
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

    host = 'https://91md.me'

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://91md.me/',
    }

    CATEGORIES = [
        ('91视频', '25'),
        ('麻豆视频', '1'),
        ('成人头条', '9'),
        ('蜜桃传媒', '4'),
        ('皇家华人', '5'),
        ('星空传媒', '6'),
        ('精东影业', '7'),
        ('乐播传媒', '8'),
        ('91制片厂', '2'),
        ('乌鸦传媒', '10'),
        ('兔子先生', '20'),
        ('杏吧原创', '21'),
        ('玩偶姐姐', '22'),
        ('mini传媒', '23'),
        ('天美传媒', '3'),
        ('大象传媒', '24'),
        ('萝莉社', '29'),
        ('PsychoPorn', '26'),
        ('糖心Vlog', '27'),
        ('性视界', '30'),
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
        classes = [{'type_name': name, 'type_id': tid} for name, tid in self.CATEGORIES]
        raw = self._get('/')
        return {'class': classes, 'list': self._getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        url = self._list_url((tid or '').strip(), pg)
        raw = self._get(url)
        lst = self._getlist(raw)
        return {
            'list': lst,
            'page': pg,
            'pagecount': 9999,
            'limit': len(lst),
            'total': 999999,
        }

    def _list_url(self, tid, pg):
        if pg <= 1:
            return f'/index.php/vod/type/id/{tid}.html'
        return f'/index.php/vod/type/id/{tid}/page/{pg}.html'

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid)
        return {'list': [self._parse_play(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        url = f'/index.php/vod/search.html?wd={kw}' if pg <= 1 else f'/index.php/vod/search/page/{pg}/wd/{kw}.html'
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
        out, seen = [], set()
        for m in re.finditer(r'<li>(.*?)</li>', html, re.S):
            block = m.group(1)
            lm = re.search(r'href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"', block)
            if not lm:
                continue
            vid = lm.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            title = ''
            tm = re.search(r'<img[^>]+alt="([^"]*)"', block)
            if not tm:
                tm = re.search(r'<p>([^<]+)</p>', block)
            if tm:
                title = unescape(tm.group(1)).strip()
            pic = ''
            pm = re.search(r'<img[^>]+(?:src|data-src)="(https?://[^"]+)"', block)
            if pm:
                pic = pm.group(1)
            date = ''
            dm = re.search(r'<i>([^<]*)</i>', block)
            if dm:
                date = dm.group(1).strip()
            if not title:
                continue
            out.append({'vod_id': self.host + lm.group(1), 'vod_name': title, 'vod_pic': pic, 'vod_remarks': date})
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
                name = unescape(m.group(1)).strip().split(' - ')[0].strip()

        pic = ''
        if m3u8:
            pic = m3u8.rsplit('/', 1)[0] + '/vod.jpg'

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
