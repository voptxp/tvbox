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
        self.proxy = ""
        if extend:
            try:
                cfg = json.loads(extend)
                self.proxy = (cfg.get("proxy") or "").rstrip("/")
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

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    host = "https://www.125av.cc"
    proxy = ""

    def homeContent(self, filter):
        data = self.getpq('')
        result = {}
        classes = []
        seen = set()
        for a in data('a[href^="/vodtype/"]').items():
            href = a.attr('href')
            name = a.text().strip()
            if not href or href in seen or not name:
                continue
            seen.add(href)
            classes.append({'type_name': name, 'type_id': href})
        result['class'] = classes
        result['list'] = self.getlist(data('section.item-box'))
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        m = re.search(r'/vodtype/(\d+)', tid)
        if not m:
            return {'list': [], 'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 999999}
        path = f"/vodtype/{m.group(1)}-{pg}.html"
        data = self.getpq(path)
        result = {}
        result['list'] = self.getlist(data('section.item-box'))
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('h1').text().strip()
        if not vod_name:
            vod_name = self.player_data(data).get('vod_name', '')
        date = data('.place').text().strip()
        if date.startswith('更新日期'):
            date = date.replace('更新日期：', '').replace('更新日期:', '').strip()

        vod = {
            'vod_name': vod_name,
            'type_name': self.player_vod_class(data),
            'vod_remarks': date,
            'vod_content': vod_name,
            'vod_play_from': '125AV',
            'vod_play_url': f"正片${ids[0]}"
        }
        pic = data('.info-video-box img').attr('src')
        if pic:
            vod['vod_pic'] = pic
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        kw = quote(key)
        path = f"/vodsearch/{kw}-/page/{pg}.html"
        data = self.getpq(path)
        return {'list': self.getlist(data('section.item-box'))}

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
            play_url = f"{self.proxy}?url={quote(url, safe='')}" if self.proxy else url
            headers = {
                'origin': self.host,
                'referer': f'{self.host}/',
                'user-agent': self.headers.get('user-agent', '')
            }
            return {'parse': 0, 'url': play_url, 'header': headers}
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

    def player_data(self, data):
        text = data.html()
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', text, re.S)
        if not m:
            return {}
        try:
            cfg = json.loads(m.group(1))
            return cfg.get('vod_data', {})
        except Exception:
            return {}

    def player_vod_class(self, data):
        cls = self.player_data(data).get('vod_class', '')
        return cls.replace(',', ' / ') if cls else ''

    def getlist(self, data):
        videos = []
        for i in data.items():
            a = i('h2 a') or i('a.img-box')
            href = a.attr('href')
            if not href:
                continue
            title = a.attr('title') or i('h2 a').text().strip()
            pic = i('.img-box img').attr('src') or i('img').attr('src') or ''
            date = i('.item-auxiliary small').text().strip()
            videos.append({
                'vod_id': href,
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