# -*- coding: utf-8 -*-
# 每日大赛 (www.mrds66.com) TVBox 采集爬虫（Typecho + DPlayer，HLS m3u8）
#
# 结构（UTF-8）：
#   首页     /
#   分类     /category/{slug}/        分页 /category/{slug}/{N}/
#   详情     /archives/{id}/
#   搜索     /search/{kw}/            分页 /search/{kw}/{N}/
#
# 播放地址：详情页 data-config 里的 m3u8 是带签名、有时效的，需实时抓取。
# 注意：本站封面图是 AES 加密的（站点 JS 用 CryptoJS 解密后显示），
#       TVBox 无法直接显示，故 vod_pic 置空。
import json
import sys
import requests
from html import unescape
from urllib.parse import quote
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.mrds66.com'

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.mrds66.com/',
    }

    CATEGORIES = [
        ('mrds', '每日大赛'),
        ('ztds', '主题大赛'),
        ('rstt', '热搜吃瓜'),
        ('xazd', '校园学生'),
        ('blyp', '必撸大赛'),
        ('fctg', '反差泄密'),
        ('mhds', '网红黑料'),
        ('lqdp', '猎奇重口'),
        ('jdsj', 'AV看片'),
        ('mxwh', '明星大赛'),
        ('smdh', '动漫之家'),
        ('dypd', '影视国漫'),
        ('mtds', 'cos写真'),
        ('ysds', '声控ASMR'),
        ('czds', '寸止挑战'),
        ('hjds', '混剪PMV'),
        ('tgds', '原创投稿'),
        ('omjp', '欧美精品'),
        ('qwcs', '全网参赛'),
        ('aijc', 'AI剧场'),
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
        r = self._session.get(url, headers=h, timeout=15)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text

    def getpq(self, path='', referer=None):
        data = self._get(path, referer)
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        raw = self._get('/')
        data = pq(raw)
        classes = [{'type_name': name, 'type_id': '/category/' + slug + '/'} for slug, name in self.CATEGORIES]
        return {'class': classes, 'list': self.getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        raw = self._get(self._page_path(tid, pg))
        return {
            'list': self.getlist(raw),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _page_path(self, tid, pg):
        tid = (tid or '').strip()
        if not tid:
            tid = '/'
        if pg <= 1:
            return tid
        if tid == '/':
            return f'/page/{pg}/'
        if not tid.endswith('/'):
            tid = tid + '/'
        return f'{tid}{pg}/'

    def detailContent(self, ids):
        vid = ids[0] if ids else 'NOIDS'
        try:
            raw = self._get(vid)
            data = pq(raw)
            vod_name = data('meta[property="og:title"]').attr('content') or ''
            if not vod_name:
                vod_name = data('meta[itemprop="headline"]').attr('content') or ''
            if not vod_name:
                vod_name = data('title').text().strip()

            desc = data('meta[property="og:description"]').attr('content') or ''
            rel = data('meta[itemprop="dateModified"]').attr('content') or ''
            if rel:
                rel = rel[:10]

            urls = self._extract_m3u8(raw)
            lines = []
            seen = set()
            counts = {}
            for u in urls:
                if u in seen:
                    continue
                seen.add(u)
                base = 'H265' if '/m3m/' in u else '高清'
                n = counts.get(base, 0) + 1
                counts[base] = n
                label = base if n == 1 else base + str(n)
                lines.append(label + chr(36) + u)

            play_from = ''
            play_url = ''
            if lines:
                play_from = '在线'
                play_url = '#'.join(lines)

            vod = {
                'vod_name': vod_name,
                'vod_pic': '',
                'vod_content': desc or vod_name,
                'vod_remarks': rel,
                'vod_play_from': play_from,
                'vod_play_url': play_url,
            }
            return {'list': [vod]}
        except Exception as e:
            return {'list': [{
                'vod_name': 'ERR:' + str(vid),
                'vod_pic': '',
                'vod_content': 'EXC:' + repr(e),
                'vod_remarks': '',
                'vod_play_from': '',
                'vod_play_url': '',
            }]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        path = f'/search/{kw}/' if pg <= 1 else f'/search/{kw}/{pg}/'
        try:
            raw = self._get(path)
            return {'list': self.getlist(raw)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith('http'):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def _extract_m3u8(self, raw):
        urls = []
        seen = set()
        pos = 0
        bs = chr(92)
        while True:
            i = raw.find('.m3u8', pos)
            if i < 0:
                break
            start = raw.rfind('https', 0, i)
            if start < 0:
                start = i - 200
                if start < 0:
                    start = 0
            end = raw.find('"', i + 5)
            if end < 0:
                end = i + 220
            u = raw[start:end]
            u = u.replace(bs + '/', '/').strip()
            if 'm3u8' in u and u.startswith('http') and u not in seen:
                seen.add(u)
                urls.append(u)
            pos = i + 5
        return urls

    def getlist(self, html):
        videos = []
        seen = set()
        parts = html.split('<article ')
        for part in parts[1:]:
            block = part.split('</article>', 1)[0]
            if 'BlogPosting' not in block:
                continue
            href = ''
            i = block.find('href="/archives/')
            if i >= 0:
                i += 6
                j = block.find('"', i)
                if j >= 0:
                    href = block[i:j]
            if not href or href in seen:
                continue
            seen.add(href)

            title = ''
            i = block.find('itemprop="headline">')
            if i >= 0:
                i += len('itemprop="headline">')
                j = block.find('<div', i)
                if j < 0:
                    j = block.find('</h2>', i)
                if j >= 0:
                    title = unescape(block[i:j]).strip()
            if not title:
                continue

            date = ''
            i = block.find('itemprop="datePublished"')
            if i >= 0:
                i = block.find('>', i)
                if i >= 0:
                    j = block.find('<', i + 1)
                    if j >= 0:
                        date = block[i + 1:j].strip()
            if date:
                date = date.replace('•', '').replace('·', '').strip()

            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': '',
                'vod_remarks': date,
            })
        return videos
