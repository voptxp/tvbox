# -*- coding: utf-8 -*-
# by @Codex
import re
import json
from urllib.parse import quote
from pyquery import PyQuery as pq
import sys
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

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

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    host = "https://www.madou.io"

    def homeContent(self, filter):
        data = self.getpq('')
        result = {}
        classes = []
        for a in data('.detail_left ol.block a.nav-link').items():
            href = a.attr('href')
            name = a.text().strip()
            if not href or href == '/' or name in ('网站首页',):
                continue
            classes.append({
                'type_name': name,
                'type_id': href
            })
        result['class'] = classes
        result['list'] = self.getlist(data('.detail_right_div ul li'))
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        base = tid[:-5] if tid.endswith('.html') else tid
        path = f"{base}/page/{pg}.html"
        data = self.getpq(path)
        result = {}
        result['list'] = self.getlist(data('.detail_right_div ul li'))
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        d = data('#detail-box')
        vod_name = d('.detail-title h1').text().strip()
        vod = {
            'vod_name': vod_name,
            'vod_pic': d('.detail-pic img').attr('src'),
            'type_name': self.meta(d, '类型'),
            'vod_year': self.meta(d, '年份'),
            'vod_area': self.meta(d, '地区'),
            'vod_remarks': d('#addtime').text().strip() or self.meta(d, '状态'),
            'vod_content': self.content(data, d, vod_name),
            'vod_play_from': '',
            'vod_play_url': ''
        }

        froms = []
        urls = []
        for group in data('[id^="playlist"]').items():
            flag = group('.down-title h2').text().strip() or '麻豆'
            eps = []
            for a in group('.video_list a').items():
                name = a.text().strip()
                href = a.attr('href')
                if not href:
                    continue
                if name == '':
                    name = '正片'
                eps.append(f"{name}${href}")
            if eps:
                froms.append(flag)
                urls.append('#'.join(eps))

        if not froms:
            froms = ['麻豆']
            urls = [f"{vod_name}${ids[0]}"]

        vod['vod_play_from'] = '$$$'.join(froms)
        vod['vod_play_url'] = '$$$'.join(urls)
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        kw = quote(key)
        if pg and str(pg) != '1':
            path = f"/index.php/vod/search/page/{pg}/wd/{kw}.html"
        else:
            path = f"/index.php/vod/search.html?wd={kw}"
        data = self.getpq(path)
        return {'list': self.getlist(data('.detail_right_div ul li'))}

    def playerContent(self, flag, id, vipFlags):
        page_url = id if id.startswith('http') else f"{self.host}{id}"
        try:
            html = self.fetch(page_url, headers=self.headers).text
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if not m:
                raise Exception('未找到播放器配置')
            cfg = json.loads(m.group(1))
            url = cfg.get('url') or ''
            if not url:
                raise Exception('未找到播放地址')
            headers = {
                'origin': self.host,
                'referer': f'{self.host}/',
                'user-agent': self.headers.get('user-agent', '')
            }
            return {'parse': 0, 'url': url, 'header': headers}
        except Exception as e:
            headers = {
                'origin': self.host,
                'referer': f'{self.host}/',
                'user-agent': self.headers.get('user-agent', '')
            }
            return {'parse': 1, 'url': page_url, 'header': headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def content(self, data, d, vod_name):
        text = data('#juqing .tjuqing').text().strip()
        if not text:
            text = self.meta(d, '剧情')
        if not text or text.startswith('…') or '详细剧情' in text:
            return vod_name
        return text
    def meta(self, d, label):
        text = d(f'dl:contains("{label}") dd').text().strip()
        if text == '未知':
            return ''
        return text

    def to_detail_id(self, href):
        if not href:
            return ''
        if 'vod/detail/id/' in href:
            return href
        m = re.search(r'/play/id/(\d+)/', href)
        if m:
            return f"/index.php/vod/detail/id/{m.group(1)}.html"
        return href

    def getlist(self, data):
        videos = []
        for i in data.items():
            href = i('p.img a').attr('href') or i('a').attr('href')
            if not href:
                continue
            vod_id = self.to_detail_id(href)
            title = i('p').eq(1).text().strip() or i('p.img img').attr('alt') or i('img').attr('alt') or ''
            pic = i('p.img img').attr('src') or i('img').attr('src') or ''
            date = i('i').text().strip()
            videos.append({
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': date
            })
        return videos

    def getpq(self, path=''):
        url = path if path.startswith('http') else f"{self.host}{path}"
        data = self.fetch(url, headers=self.headers).text
        try:
            return pq(data)
        except Exception as e:
            print(str(e))
            return pq(data.encode('utf-8'))