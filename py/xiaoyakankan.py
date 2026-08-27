# -*- coding: utf-8 -*-
# 小鸭看看 (xiaoyakankan.com) TVBox 采集爬虫（福利/情色片）
#
# 结构：
#   首页   /                           (.item 列表)
#   福利   /cat/15.html                (福利首页，含分类导航 + 福利列表)
#   分类   /cat/{id}.html              分页 /cat/{id}-{page}.html
#   详情   /post/{hexid}.html          (h1/封面/简介 + var pp={...} 播放线路)
#
# 播放地址：详情页内嵌 JS： var pp={"no":..,"lines":[["id","线路名",1,["m3u8地址"]]]}
import re
import json
import sys
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://xiaoyakankan.com"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://xiaoyakankan.com/',
    }

    def init(self, extend=""):
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
    def _get(self, path):
        url = path if path.startswith('http') else f"{self.host}{path}"
        return self.fetch(url, headers=self.headers).text

    def getpq(self, path=''):
        data = self._get(path)
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        data = self.getpq('/cat/15.html')
        classes = []
        seen = set()
        for a in data('a[href^="/cat/"]').items():
            href = a.attr('href')
            name = a.text().strip()
            if not href or not name:
                continue
            if re.match(r'^/cat/15\d{0,2}\.html$', href) and href not in seen:
                seen.add(href)
                classes.append({'type_name': name, 'type_id': href})
        classes.sort(key=lambda c: (c['type_id'] != '/cat/15.html', c['type_id']))
        return {'class': classes, 'list': self.getlist(data('div.item'))}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        data = self.getpq(self._page_path(tid, pg))
        return {
            'list': self.getlist(data('div.item')),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _page_path(self, tid, pg):
        tid = (tid or '').strip()
        if not tid.endswith('.html'):
            return '/'
        base = tid[:-5]
        if pg <= 1:
            return base + '.html'
        return f'{base}-{pg}.html'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('h1').text().strip()
        poster = data('#awp1').attr('data-poster') or data('meta[property="og:image"]').attr('content') or ''
        if poster.startswith('//'):
            poster = 'https:' + poster
        desc = data('meta[name="description"]').attr('content') or ''

        play_from = ''
        play_url = ''
        m = re.search(r'var\s+pp\s*=\s*(\{.*?\})', data.html(), re.S)
        if m:
            try:
                pp = json.loads(m.group(1))
                froms = []
                urls = []
                for line in pp.get('lines', []):
                    if len(line) < 4:
                        continue
                    name = line[1]
                    urllist = line[3] or []
                    if not urllist:
                        continue
                    froms.append(name)
                    eps = []
                    for i, u in enumerate(urllist):
                        epname = '正片' if len(urllist) == 1 else f'第{i + 1}集'
                        eps.append(f'{epname}${u}')
                    urls.append('#'.join(eps))
                play_from = '$$$'.join(froms)
                play_url = '$$$'.join(urls)
            except Exception:
                pass

        vod = {
            'vod_name': vod_name,
            'vod_pic': poster,
            'vod_content': desc or vod_name,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith('http') else id
        return {
            'parse': 0,
            'jx': 0,
            'url': url,
            'header': {
                'user-agent': self.USER_AGENT,
                'referer': self.host + '/',
            },
        }

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def getlist(self, data):
        videos = []
        for it in data.items():
            a = it('a.link')
            href = a.attr('href')
            if not href:
                continue
            title = it('.info .title').text().strip() or a('img').attr('alt') or ''
            pic = a('img').attr('data-src') or a('img').attr('src') or ''
            if pic.startswith('//'):
                pic = 'https:' + pic
            remarks = it('.tag2').text().strip() or it('.tag1').text().strip() or ''
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })
        return videos
