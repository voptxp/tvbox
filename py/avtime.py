# -*- coding: utf-8 -*-
# AV时间 (avtime.tv) TVBox 采集爬虫（maccms）
#
# 分类页：/vodshow/{typeid}-----------/          (第1页)
#          /vodshow/{typeid}--------{N}---/      (第N页)
# 播放页：/vodplay/{id}-{sid}-{nid}/
# 播放地址：播放页 var player_aaaa={...} 里 url 字段
#          encrypt=0 明文 / 1=urlencode / 2=base64(urlencode)
# 海报：由 m3u8 地址推导（同目录 1.jpg）
import base64
import json
import re
import sys
import requests
from html import unescape
from urllib.parse import unquote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.avtime.tv'

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.avtime.tv/',
    }

    CATEGORIES = [
        ('伦理片', '25'),
        ('日本中字', '51'),
        ('国产', '20'),
        ('动漫', '24'),
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
        raw = self._get('/vodshow/25-----------/')
        return {'class': classes, 'list': self._getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        url = self._list_url((tid or '').strip(), pg)
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

    def _list_url(self, tid, pg):
        if pg <= 1:
            return f'/vodshow/{tid}-----------/'
        return f'/vodshow/{tid}--------{pg}---/'

    def _pagecount(self, raw):
        nums = [int(x) for x in re.findall(r'/vodshow/\d+--------(\d+)---/', raw)]
        return max(nums) if nums else 1

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid)
        return {'list': [self._parse_play(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        if '.m3u8' in url:
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析
    def _getlist(self, html):
        out = []
        seen = set()
        for m in re.finditer(r'<a href="(/vodplay/\d+-\d+-\d+/)"[^>]*class="card[^"]*"[^>]*>(.*?)</a>', html, re.S):
            url = m.group(1)
            block = m.group(2)
            if url in seen:
                continue
            seen.add(url)
            title = ''
            tm = re.search(r'<div class="desc">([^<]*)</div>', block)
            if tm:
                title = unescape(tm.group(1)).strip()
            pic = ''
            pm = re.search(r'data-src="(https?://[^"]+)"', block)
            if pm:
                pic = pm.group(1)
            remarks = ''
            rm = re.search(r'<div class="play-time">([^<]*)</div>', block)
            if rm:
                remarks = rm.group(1).strip()
            if not title:
                continue
            out.append({'vod_id': self.host + url, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remarks})
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
        vclass = vd.get('vod_class') or ''
        m3u8 = self._decode_url(data.get('url') or '', data.get('encrypt', 0))

        if not name:
            m = re.search(r'<title>(.*?)</title>', raw, re.S)
            if m:
                name = unescape(m.group(1)).strip()
                name = re.sub(r'^.*?《', '', name)
                name = name.split('》')[0]

        pic = ''
        if m3u8:
            pic = m3u8.rsplit('/', 1)[0] + '/1.jpg'

        desc = ''
        if vclass:
            desc = '分类: ' + vclass
        if name:
            desc = (desc + '\n' if desc else '') + name

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
