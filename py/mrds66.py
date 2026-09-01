# -*- coding: utf-8 -*-
# 每日大赛 (www.mrds66.com) TVBox 采集爬虫（Typecho + DPlayer，HLS m3u8）
#
# 结构（UTF-8）：
#   首页     /
#   分类     /category/{slug}/        分页 /category/{slug}/{N}/
#   详情     /archives/{id}/
#   搜索     /search/{kw}/            分页 /search/{kw}/{N}/
#
# 播放地址：详情页每个 .dplayer 的 data-config（JSON）里含：
#   video      -> 高清 m3u8（/videos5/...）
#   video_h265 -> H265 m3u8（/m3m/...，可能为空）
# 一个页面可能出现多个 .dplayer：
#   * 普通影片：1 个窗口（高清 + H265）
#   * 一页多集：N 个窗口，标题带“X-Y集 / 第X集 / 合集” -> 每个窗口一集
#   * 多线路：  N 个窗口，标题无集数 -> 每条线路一个窗口
# 全部用字符串解析 + 内置 json，不依赖 lxml/pyquery，避免 TVBox 内置环境编码误判报错。
import json
import re
import sys
import requests
from html import unescape
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.mrds66.com'

    img_proxy = ''

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
        r = self._session.get(url, headers=h, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        raw = self._get('/')
        classes = [{'type_name': name, 'type_id': '/category/' + slug + '/'} for slug, name in self.CATEGORIES]
        return {'class': classes, 'list': self.getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        raw = self._get(self._page_path(tid, pg))
        lst = self.getlist(raw)
        pc = self._pagecount(raw)
        return {
            'list': lst,
            'page': pg,
            'pagecount': pc,
            'limit': len(lst),
            'total': pc * len(lst) if lst else 0,
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

    def _pagecount(self, raw):
        i = raw.find('page-info')
        if i >= 0:
            j = raw.find('/', i)
            k = raw.find('<', j)
            if j >= 0 and k >= 0:
                n = raw[j + 1:k].strip()
                if n.isdigit() and int(n) > 0:
                    return int(n)
        return 9999

    def detailContent(self, ids):
        vid = ids[0] if ids else ''
        raw = self._get(vid)

        vod_name = self._meta_content(raw, 'property="og:title"') or self._meta_content(raw, 'itemprop="headline"') or ''
        if not vod_name:
            i = raw.find('<title>')
            if i >= 0:
                j = raw.find('</title>', i)
                if j >= 0:
                    vod_name = unescape(raw[i + 7:j]).strip()

        desc = self._meta_content(raw, 'property="og:description"') or vod_name
        rel = self._meta_content(raw, 'itemprop="dateModified"') or ''
        if rel:
            rel = rel[:10]

        pic = ''
        i = raw.find('data-xkrkllgl="')
        if i >= 0:
            i += len('data-xkrkllgl="')
            j = raw.find('"', i)
            if j >= 0:
                pic = raw[i:j]
        pic = self._pic(pic)

        wins = self._parse_windows(raw)
        line_names, line_urls = self._build_play_lines(raw, wins)

        if not line_urls:
            urls = self._extract_m3u8(raw)
            if urls:
                counts = {}
                eps = []
                for u in urls:
                    base = 'H265' if '/m3m/' in u else '高清'
                    n = counts.get(base, 0) + 1
                    counts[base] = n
                    label = base if n == 1 else base + str(n)
                    eps.append(label + chr(36) + u)
                line_names = ['在线']
                line_urls = ['#'.join(eps)]

        vod = {
            'vod_id': vid,
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_content': desc or vod_name,
            'vod_remarks': rel,
            'vod_play_from': '$$$'.join(line_names) if line_names else '',
            'vod_play_url': '$$$'.join(line_urls) if line_urls else '',
        }
        return {'list': [vod]}

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
    def _parse_windows(self, raw):
        wins = []
        pos = 0
        while True:
            i = raw.find("data-config='", pos)
            if i < 0:
                break
            j = raw.find("'", i + len("data-config='"))
            if j < 0:
                break
            cfg = raw[i + len("data-config='"):j]
            pos = j + 1

            v = ''
            h = ''
            try:
                obj = json.loads(cfg.replace('\\/', '/'))
            except Exception:
                v = self._json_url(cfg, 'video')
                h = self._json_url(cfg, 'video_h265')
            else:
                vo = obj.get('video')
                ho = obj.get('video_h265')
                if isinstance(vo, dict):
                    v = vo.get('url') or ''
                if isinstance(ho, dict):
                    h = ho.get('url') or ''

            if not v and not h:
                continue

            tt = ''
            ti = raw.rfind('data-video_title="', 0, i)
            if ti >= 0:
                tj = raw.find('"', ti + len('data-video_title="'))
                if tj >= 0 and tj < i:
                    tt = raw[ti + len('data-video_title="'):tj]

            wins.append({'title': tt, 'video': v, 'h265': h})
        return wins

    def _json_url(self, cfg, key):
        m = re.search(r'"' + re.escape(key) + r'"\s*:\s*\{\s*"url"\s*:\s*"([^"]*)"', cfg)
        if m:
            return m.group(1).replace('\\/', '/')
        return ''

    def _build_play_lines(self, raw, wins):
        names = []
        urls = []
        if not wins:
            return names, urls

        if len(wins) == 1:
            w = wins[0]
            eps = []
            if w['video']:
                eps.append('高清' + chr(36) + w['video'])
            if w['h265']:
                eps.append('H265' + chr(36) + w['h265'])
            if eps:
                names = ['在线']
                urls = ['#'.join(eps)]
            return names, urls

        # 多个窗口
        if self._is_episode_page(raw):
            labels = self._episode_labels(raw, len(wins))
            hd = []
            hv = []
            for i, w in enumerate(wins):
                lb = labels[i] if i < len(labels) else ('第%d集' % (i + 1))
                if w['video']:
                    hd.append(lb + chr(36) + w['video'])
                if w['h265']:
                    hv.append(lb + chr(36) + w['h265'])
            if hd:
                names.append('高清')
                urls.append('#'.join(hd))
            if hv:
                names.append('H265')
                urls.append('#'.join(hv))
        else:
            for i, w in enumerate(wins):
                eps = []
                if w['video']:
                    eps.append('高清' + chr(36) + w['video'])
                if w['h265']:
                    eps.append('H265' + chr(36) + w['h265'])
                if eps:
                    names.append('线路%d' % (i + 1))
                    urls.append('#'.join(eps))
        return names, urls

    def _is_episode_page(self, raw):
        title = self._meta_content(raw, 'property="og:title"') or ''
        return ('集' in title) or ('合集' in title)

    def _episode_labels(self, raw, n):
        title = self._meta_content(raw, 'property="og:title"') or ''
        m = re.search(r'(\d+)\s*[-—~～至到]\s*(\d+)\s*集', title)
        if m:
            a = int(m.group(1))
            b = int(m.group(2))
            if b - a + 1 == n:
                return ['第%d集' % x for x in range(a, b + 1)]
            return ['第%d集' % x for x in range(a, a + n)]
        return ['第%d集' % (i + 1) for i in range(n)]

    def _pic(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            url = 'https:' + url
        if self.img_proxy and (url.startswith('https://pic.xustgq.cn/') or url.startswith('https://pic.sbhioa.cn/')):
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

            pic = ''
            i = block.find("loadBannerDirect('")
            if i >= 0:
                i += len("loadBannerDirect('")
                j = block.find("'", i)
                if j >= 0:
                    pic = block[i:j]
            pic = self._pic(pic)

            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': date,
            })
        return videos
