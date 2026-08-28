# -*- coding: utf-8 -*-
# JavBus (www.javbus.com) TVBox 采集爬虫（磁力下载站）
#
# 结构（UTF-8）：
#   首页有码    /
#   无码        /uncensored
#   高清        /genre/hd
#   字幕        /genre/sub
#   分页        /page/{n}  /uncensored/page/{n}  /genre/hd/{n}  /genre/sub/{n}
#   详情        /{ID}
#   磁力        AJAX /ajax/uncledatoolsbyajax.php?gid={gid}&uc=0&lang=zh
#   搜索        /search/{kw}  分页 /search/{kw}/{n}
#
# 播放地址：magnet:?xt=urn:btih:...（多磁力，含 高清/字幕/容量）
import re
import json
import sys
import requests
from urllib.parse import quote
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.javbus.com'

    img_proxy = ''
    TRACKERS = [
        'udp://tracker.opentrackr.org:1337/announce',
        'udp://open.tracker.cl:1337/announce',
        'udp://tracker.torrent.eu.org:451/announce',
        'udp://explodie.org:6969/announce',
        'udp://exodus.desync.com:6969/announce',
    ]

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.javbus.com/',
    }

    CATEGORIES = [
        ('/', '有碼最新'),
        ('/uncensored', '無碼最新'),
        ('/genre/hd', '高清'),
        ('/genre/sub', '字幕'),
    ]

    def init(self, extend=''):
        self.img_proxy = ''
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                self.img_proxy = (cfg.get('img_proxy') or '').rstrip('/')
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

    # ------------------------------------------------------------------ 网络层
    def _get(self, path, referer=None):
        url = path if path.startswith('http') else f'{self.host}{path}'
        h = dict(self.headers)
        if referer:
            h['referer'] = referer
        try:
            r = self.fetch(url, headers=h)
            if hasattr(r, 'text'):
                return r.text
        except Exception:
            pass
        r = requests.get(url, headers=h, timeout=15)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text

    def getpq(self, path='', referer=None):
        return pq(self._get(path, referer))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        data = self.getpq('/')
        classes = [{'type_name': name, 'type_id': path} for path, name in self.CATEGORIES]
        return {'class': classes, 'list': self.getlist(data)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        data = self.getpq(self._page_path(tid, pg))
        return {
            'list': self.getlist(data),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _page_path(self, tid, pg):
        tid = (tid or '').strip().rstrip('/')
        if not tid:
            tid = '/'
        if pg <= 1:
            return tid
        if tid == '/':
            return f'/page/{pg}'
        if tid == '/uncensored':
            return f'/uncensored/page/{pg}'
        return f'{tid}/{pg}'

    def detailContent(self, ids):
        raw = self._get(ids[0])
        data = pq(raw)
        vod_name = data('h3').text().strip()
        if not vod_name:
            t = data('title').text().strip()
            vod_name = t.replace(' - JavBus', '').strip()

        pic = self._pic(data('a.bigImage img').attr('src') or '')

        fid = self._field(data, '識別碼')
        rel = self._field(data, '發行日期')
        length = self._field(data, '長度')
        studio = self._field(data, '製作商')
        publisher = self._field(data, '發行商')
        series = self._field(data, '系列')
        actors = [a.text().strip() for a in data('div.star-name a').items() if a.text().strip()]
        parts = []
        for k, v in [('識別碼', fid), ('發行日期', rel), ('長度', length),
                     ('製作商', studio), ('發行商', publisher), ('系列', series)]:
            if v:
                parts.append(f'{k}:{v}')
        if actors:
            parts.append('演員:' + '/'.join(actors))
        desc = ' | '.join(parts)

        gid_m = re.search(r'var gid = ([0-9]+);', raw)
        magnets = []
        if gid_m:
            ref = ids[0] if ids[0].startswith('http') else self.host + ids[0]
            mag_html = self._get(f'/ajax/uncledatoolsbyajax.php?gid={gid_m.group(1)}&uc=0&lang=zh', referer=ref)
            magnets = self._parse_magnets(pq(mag_html))

        play_from = ''
        play_url = ''
        if magnets:
            play_from = '磁力'
            lines = []
            used = {}
            for i, m in enumerate(magnets):
                label = m['label'] or f'磁力{i + 1}'
                n = used.get(label, 0) + 1
                used[label] = n
                if n > 1:
                    label = f'{label} {n}'
                url = m['url']
                lines.append(f'{label}${url}')
            play_url = '#'.join(lines)

        vod = {
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_content': desc or vod_name,
            'vod_remarks': rel or fid or '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote(key, safe='').replace('%20', '+')
        path = f'/search/{kw}' if pg <= 1 else f'/search/{kw}/{pg}'
        try:
            data = self.getpq(path)
            return {'list': self.getlist(data)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith('magnet:'):
            url = self._with_trackers(url)
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {}}
        if url.startswith('ed2k:') or url.startswith('thunder:'):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def _field(self, data, name):
        for p in data('div.info > p').items():
            h = p('span.header').eq(0)
            if h.length and h.text().strip().rstrip(':') == name:
                full = p.text().strip()
                return full.replace(h.text().strip(), '', 1).strip()
        return ''

    def _pic(self, url):
        if not url:
            return url
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = self.host + url
        if self.img_proxy and url.startswith(self.host + '/pics/'):
            return self.img_proxy + '?url=' + quote(url, safe='')
        return url

    def _with_trackers(self, url):
        if '&tr=' in url:
            return url
        return url + ''.join('&tr=' + quote(t, safe='') for t in self.TRACKERS)

    def _parse_magnets(self, data):
        magnets = []
        seen = set()
        for tr in data('tr').items():
            mag_url = ''
            for a in tr('a').items():
                href = a.attr('href') or ''
                if href.startswith('magnet:'):
                    mag_url = href
                    break
            if not mag_url or mag_url in seen:
                continue
            seen.add(mag_url)
            mag_url = self._with_trackers(mag_url)
            first_td = tr('td').eq(0)
            badges = []
            for b in first_td('a').items():
                cls = b.attr('class') or ''
                t = b.text().strip()
                if 'btn' in cls and t and t not in badges:
                    badges.append(t)
            size = tr('td').eq(1).text().strip()
            date = tr('td').eq(2).text().strip()
            label = ' '.join(badges + ([size] if size else [])).strip()
            magnets.append({'label': label, 'url': mag_url, 'size': size, 'date': date, 'badges': badges})
        return magnets

    def getlist(self, data):
        videos = []
        seen = set()
        for a in data('#waterfall a.movie-box').items():
            href = a.attr('href') or ''
            if not href or href in seen:
                continue
            seen.add(href)
            img = a('img').eq(0)
            title = img.attr('title') or ''
            pic = self._pic(img.attr('src') or '')
            dates = a('.photo-info date')
            date = dates.eq(dates.length - 1).text().strip() if dates.length else ''
            if not title:
                title = a('.photo-info span').eq(0).text().strip()
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': date,
            })
        return videos

