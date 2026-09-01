# -*- coding: utf-8 -*-
# 麻豆不打烊 (mdbdy.com) TVBox 采集爬虫（Typecho + DPlayer）
#
# 结构：
#   分类   /category/{slug}/            分页 /category/{slug}/{N}/
#   详情   /archives/{id}/
#   播放   /play-url/{cid}.json?i={index}  -> JSON data.url (签名 m3u8)
#
# 详情页可能有一个或多个 .dplayer：
#   * 普通影片：1 个 dplayer，data-player-index=0
#   * 一页多集：N 个 dplayer，同一个 data-video-id，index 依次 0..N-1
# 全部用字符串解析 + 内置 json，不依赖 lxml/pyquery。
import json
import re
import sys
import requests
from html import unescape
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://mdbdy.com'

    img_proxy = ''

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://mdbdy.com/',
    }

    CATEGORIES = [
        ('今日热搜', '/category/17202/'),
        ('今日大赛', '/category/189010101/'),
        ('AI短剧', '/category/216010101/'),
        ('学生校园', '/category/14202/'),
        ('必吃大瓜', '/category/17521/'),
        ('明星黑料', '/category/14203/'),
        ('网红黑料', '/category/214710102/'),
        ('国产剧情', '/category/810101/'),
        ('人妻互换NTR', '/category/810102/'),
        ('海角社区', '/category/810103/'),
        ('反差黑料', '/category/810104/'),
        ('重口味', '/category/810105/'),
        ('里番动漫', '/category/810106/'),
        ('麻豆传媒', '/category/14205/'),
        ('探花偷拍', '/category/216010102/'),
        ('AV解说', '/category/218310101/'),
        ('世界杯合集', '/category/312010101/'),
    ]

    def init(self, extend=''):
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self.img_proxy = 'http://192.168.0.3/mrds66_img.php'
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if cfg.get('img_proxy'):
                    self.img_proxy = cfg['img_proxy'].rstrip('/')
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
        h = {'referer': referer} if referer else {}
        r = self._session.get(url, headers=h, timeout=20)
        r.encoding = 'utf-8'
        return r.text

    def _get_json(self, path):
        r = self._session.get(path, headers={'accept': 'application/json,text/plain,*/*'}, timeout=20)
        try:
            return r.json()
        except Exception:
            return {}

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
        return f'{u}/{pg}/'

    def _pagecount(self, raw):
        m = re.search(r'data-total-page="(\d+)"', raw)
        if m:
            return int(m.group(1))
        m = re.search(r'page-info[^>]*>\s*(\d+)/(\d+)', raw)
        if m:
            return int(m.group(2))
        nums = [int(x) for x in re.findall(r'/category/\d+/(\d+)/', raw)]
        return max(nums) if nums else 1

    def detailContent(self, ids):
        vid = (ids[0] if ids else '').strip()
        if not vid:
            return {'list': []}
        raw = self._get(vid)
        return {'list': [self._parse_detail(vid, raw)]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        path = f'/search/{kw}/' if pg <= 1 else f'/search/{kw}/{pg}/'
        try:
            raw = self._get(path)
            return {'list': self._getlist(raw)}
        except Exception:
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

    # ------------------------------------------------------------------ 列表解析
    def _getlist(self, html):
        out = []
        seen = set()
        parts = html.split('<article ')
        for part in parts[1:]:
            block = part.split('</article>', 1)[0]
            if 'BlogPosting' not in block:
                continue
            lm = re.search(r'href="(/archives/\d+/)"', block)
            if not lm:
                continue
            url = self.host + lm.group(1)
            if url in seen:
                continue
            seen.add(url)

            title = ''
            tm = re.search(r'itemprop="headline">([^<]*)<', block)
            if not tm:
                tm = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.S)
                if tm:
                    title = unescape(re.sub(r'<[^>]+>', '', tm.group(1))).strip()
            else:
                title = unescape(tm.group(1)).strip()
            if not title:
                continue

            pic = ''
            pm = re.search(r'data-bg="(https?://[^"]+)"', block)
            if not pm:
                pm = re.search(r'data-src="(https?://[^"]+)"', block)
            if pm:
                pic = self._pic(pm.group(1))

            date = ''
            dm = re.search(r'itemprop="datePublished"[^>]*content="([^"]+)"', block)
            if dm:
                date = dm.group(1)[:10]

            out.append({'vod_id': url, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': date})
        return out

    # ------------------------------------------------------------------ 详情解析
    def _parse_detail(self, vid, raw):
        cids = re.findall(r'data-video-id="([^"]+)"', raw)
        indices = re.findall(r'data-player-index="([^"]+)"', raw)
        cid = cids[0] if cids else ''

        name = self._meta_content(raw, 'property="og:title"') or self._title(raw)
        desc = self._meta_content(raw, 'property="og:description"') or name

        pic = ''
        m = re.search(r'data-cover="(https?://[^"]+)"', raw)
        if not m:
            m = re.search(r'data-bg="(https?://[^"]+)"', raw)
        if m:
            pic = self._pic(m.group(1))

        if not indices:
            indices = ['0']

        lines = []
        seen = set()
        for i, idx in enumerate(indices):
            u = self._play_m3u8(cid, idx)
            if not u or u in seen:
                continue
            seen.add(u)
            label = '高清' if len(indices) == 1 else ('第%d集' % (i + 1))
            lines.append(label + chr(36) + u)

        play_from = ''
        play_url = ''
        if lines:
            play_from = '在线'
            play_url = '#'.join(lines)

        return {
            'vod_id': vid,
            'vod_name': name or vid,
            'vod_pic': pic,
            'vod_content': desc or name,
            'vod_remarks': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _play_m3u8(self, cid, idx):
        if not cid:
            return ''
        data = self._get_json(f'{self.host}/play-url/{cid}.json?i={idx}')
        if not data or data.get('code') != 0:
            return ''
        d = data.get('data') or {}
        return d.get('url') or ''

    # ------------------------------------------------------------------ 工具
    def _pic(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            url = 'https:' + url
        if self.img_proxy and (url.startswith('https://pic.sbhioa.cn/') or url.startswith('https://pic.xustgq.cn/')):
            return self.img_proxy + '?url=' + quote(url, safe='')
        return url

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
            t = unescape(m.group(1)).strip()
            t = t.split(' | ')[0].strip()
            return t
        return ''
