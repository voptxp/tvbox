# -*- coding: utf-8 -*-
# 伦理片高清平台 (www.glsbc.com) TVBox 采集爬虫（MacCMS/苹果CMS）
#
# 结构（UTF-8）：
#   首页   /                                        (.thumbnail 列表，链接直接指向播放页)
#   分类   /index.php/vod/type/id/{tid}.html         分页 /index.php/vod/type/id/{tid}/page/{pg}.html
#   播放   /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html
#          内嵌 player_aaaa={...,"url":"m3u8",...,"vod_data":{...}}
#   搜索   /index.php/vod/search.html?wd=关键词
import re
import json
import sys
import requests
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://www.glsbc.com"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.glsbc.com/',
    }

    def init(self, extend=""):
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
    def _get(self, path):
        url = path if path.startswith('http') else f"{self.host}{path}"
        r = self._session.get(url, timeout=15)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text

    def getpq(self, path=''):
        return pq(self._get(path))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        data = self.getpq('/')
        classes = []
        seen = set()
        for a in data('a[href*="/vod/type/"]').items():
            href = a.attr('href') or ''
            name = a.text().strip()
            if not name or name == '更多':
                continue
            if href in seen:
                continue
            seen.add(href)
            classes.append({'type_name': name, 'type_id': href})
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
        if pg <= 1:
            return tid or '/'
        base = tid[:-5] if tid.endswith('.html') else tid.rstrip('/')
        return f'{base}/page/{pg}.html'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        raw = data.html()
        vod_name = data('h1').text().strip()
        vod_pic = ''
        # 封面：播放页第一个 lozad 图
        for img in data('img.lozad').items():
            ds = img.attr('data-src') or ''
            if ds and ('jpg' in ds or 'png' in ds or 'webp' in ds):
                vod_pic = ds
                break
        if not vod_pic:
            vod_pic = data('meta[property="og:image"]').attr('content') or ''

        type_name = ''
        play_url = ''
        m = re.search(r'player_aaaa=(\{.*?\})\s*</script>', raw, re.S)
        if m:
            try:
                cfg = json.loads(m.group(1))
                vd = cfg.get('vod_data') or {}
                if not vod_name:
                    vod_name = vd.get('vod_name', '')
                type_name = vd.get('vod_class', '')
                play_url = cfg.get('url', '')
            except Exception:
                pass

        vod = {
            'vod_name': vod_name,
            'vod_pic': vod_pic,
            'type_name': type_name,
            'vod_content': '',
            'vod_play_from': '正片' if play_url else '',
            'vod_play_url': ('正片$' + play_url) if play_url else '',
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        try:
            r = self._session.get(
                self.host + '/index.php/vod/search.html',
                params={'wd': key, 'page': pg if pg > 1 else None},
                timeout=15,
            )
            r.encoding = r.apparent_encoding or 'utf-8'
            return {'list': self.getlist(pq(r.text))}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        return {
            'parse': 0,
            'jx': 0,
            'url': url,
            'header': {
                'User-Agent': self.USER_AGENT,
                'Referer': self.host + '/',
            },
        }

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def getlist(self, data):
        videos = []
        seen = set()
        for it in data('div.thumbnail').items():
            a = it('a[href*="/vod/play/"]').eq(0)
            href = a.attr('href') or ''
            img = a('img').eq(0)
            title = img.attr('alt') or ''
            if not title:
                title = it('a[href*="/vod/play/"]').eq(-1).text().strip()
            pic = img.attr('data-src') or img.attr('src') or ''
            if not href or not title:
                continue
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return videos

