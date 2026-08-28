# -*- coding: utf-8 -*-
# 每日大赛 (www.mrds66.com) TVBox 采集爬虫（Typecho + DPlayer，HLS m3u8）
#
# 结构（UTF-8）：
#   首页     /
#   分类     /category/{slug}/        分页 /category/{slug}/{N}/
#   详情     /archives/{id}/
#   搜索     /search/{kw}/            分页 /search/{kw}/{N}/
#
# 播放地址：详情页 <div class="dplayer" data-config='{...}'>
#   data-config 里的 video.url / video_h265.url 是带签名的 m3u8，需实时抓取
import json
import sys
import requests
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
        classes = [{'type_name': name, 'type_id': '/category/' + slug + '/'} for slug, name in self.CATEGORIES]
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
        raw = self._get(ids[0])
        data = pq(raw)
        vod_name = data('meta[property="og:title"]').attr('content') or ''
        if not vod_name:
            vod_name = data('meta[itemprop="headline"]').attr('content') or ''
        if not vod_name:
            vod_name = data('title').text().strip()

        pic = data('img[data-xkrkllgl]').eq(0).attr('data-xkrkllgl') or ''
        if not pic:
            pic = data('meta[property="og:image"]').attr('content') or ''
        if pic.startswith('//'):
            pic = 'https:' + pic

        desc = data('meta[property="og:description"]').attr('content') or ''
        rel = data('meta[itemprop="dateModified"]').attr('content') or ''
        if rel:
            rel = rel[:10]

        lines = []
        seen = set()
        dplayers = data('.dplayer')
        total = len(dplayers)
        vid_no = 0
        for dp in dplayers.items():
            cfg = dp.attr('data-config') or ''
            if not cfg:
                continue
            try:
                obj = json.loads(cfg)
            except Exception:
                continue
            vid_no += 1
            prefix = f'视频{vid_no}' if total > 1 else ''
            items = []
            v = obj.get('video') or {}
            if v.get('url'):
                items.append(('高清', v.get('url')))
            hv = obj.get('video_h265') or {}
            if hv.get('url'):
                items.append(('H265', hv.get('url')))
            for label, u in items:
                if not u or u in seen:
                    continue
                seen.add(u)
                lines.append(prefix + label + chr(36) + u)

        play_from = ''
        play_url = ''
        if lines:
            play_from = '在线'
            play_url = '#'.join(lines)

        vod = {
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_content': desc or vod_name,
            'vod_remarks': rel,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        path = f'/search/{kw}/' if pg <= 1 else f'/search/{kw}/{pg}/'
        try:
            data = self.getpq(path)
            return {'list': self.getlist(data)}
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
    def getlist(self, data):
        videos = []
        seen = set()
        for art in data('article').items():
            itemtype = art.attr('itemtype') or ''
            if 'BlogPosting' not in itemtype:
                continue
            href = ''
            for a in art.find('a').items():
                h = a.attr('href') or ''
                if '/archives/' in h:
                    href = h
                    break
            if not href or href in seen:
                continue
            seen.add(href)

            title_node = art.find('h2.post-card-title')
            title_node.find('.wraps').remove()
            title = title_node.text().strip()
            if not title:
                title = art.find('meta[itemprop="headline"]').attr('content') or ''
            if not title:
                continue

            art_html = art.html() or ''
            pic = ''
            i = art_html.find('loadBannerDirect(')
            if i >= 0:
                i = art_html.find("'", i)
                if i >= 0:
                    j = art_html.find("'", i + 1)
                    if j >= 0:
                        pic = art_html[i + 1:j]
            if pic.startswith('//'):
                pic = 'https:' + pic

            date = ''
            for sp in art.find('span').items():
                if sp.attr('itemprop') == 'datePublished':
                    date = sp.text().strip()
                    break
            if date:
                date = date.replace('•', '').replace('·', '').strip()

            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': date,
            })
        return videos
