# -*- coding: utf-8 -*-
# 韩片剧场 hanpian.me TVBox 采集爬虫（maccms / xxgw 模板）
#
# 结构：
#   全部伦理片列表   /so/ll/----------/          分页 /so/ll/-------{N}---/
#   地区筛选         /so/ll/{地区}----------/    分页 /so/ll/{地区}-------{N}---/
#   详情             /vod/{vid}/
#   播放页           /yun/{vid}/{sid}/{nid}/  （页面内 var player_aaaa={...} 的 url 字段 = m3u8）
#   搜索             /search/{kw}-------------/
#
# 播放地址：m3u8（encrypt=0 明文，实测无需 Referer）
import base64
import json
import re
import sys
import requests
from html import unescape
from urllib.parse import quote, unquote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.hanpian.me'

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.hanpian.me/',
    }

    # (显示名, 筛选地区)  —— 地区为空表示“全部”
    CATEGORIES = [
        ('全部', 'all'),
        ('大陆', '大陆'),
        ('香港', '香港'),
        ('台湾', '台湾'),
        ('俄罗斯', '俄罗斯'),
        ('美国', '美国'),
        ('日本', '日本'),
        ('韩国', '韩国'),
        ('英国', '英国'),
        ('法国', '法国'),
        ('德国', '德国'),
        ('印度', '印度'),
        ('泰国', '泰国'),
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

    # ------------------------------------------------------------------ URL 构造
    def _filter_url(self, region, pg):
        # 筛选段共 11 个字段（f0..f10），f0=地区，f7=页码，其余为空
        r = '' if (not region or region == 'all') else quote(region, safe='')
        pg = int(pg or 1)
        if pg <= 1:
            seg = r + '-' * 10
        else:
            seg = r + '-' * 7 + str(pg) + '-' * 3
        return f'/so/ll/{seg}/'

    def _last_page(self, raw):
        m = re.search(r'href="(/so/ll/[^"]*)"[^>]*>\s*尾页', raw)
        if m:
            n = re.search(r'(\d+)---/?$', m.group(1))
            if n:
                return int(n.group(1))
        nums = [int(x) for x in re.findall(r'------(\d+)---', raw)]
        return max(nums) if nums else 1

    def _abs(self, url):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        classes = [{'type_name': name, 'type_id': tid} for name, tid in self.CATEGORIES]
        raw = self._get(self._filter_url('all', 1))
        return {'class': classes, 'list': self._getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        region = (tid or '').strip() or 'all'
        raw = self._get(self._filter_url(region, pg))
        lst = self._getlist(raw)
        return {
            'list': lst,
            'page': pg,
            'pagecount': self._last_page(raw),
            'limit': len(lst),
            'total': self._last_page(raw) * max(len(lst), 1),
        }

    def detailContent(self, ids):
        vid_path = (ids[0] if ids else '').strip()
        if not vid_path:
            return {'list': []}
        raw = self._get(vid_path)
        return {'list': [self._parse_detail(vid_path, raw)]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        if not kw:
            return {'list': []}
        url = f'/search/{kw}-------------/'
        try:
            raw = self._get(url)
        except Exception:
            return {'list': []}
        return {'list': self._getlist_search(raw)}

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        if not url:
            return {'parse': 1, 'jx': 0, 'url': '', 'header': {'user-agent': self.USER_AGENT}}
        # 已经是直链 m3u8 / mp4
        if url.startswith('http') and '/yun/' not in url:
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}
        if '/yun/' in url:
            try:
                raw = self._get(url)
            except Exception:
                return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}
            m3u8 = self._extract_m3u8(raw)
            if m3u8:
                return {'parse': 0, 'jx': 0, 'url': m3u8, 'header': {'user-agent': self.USER_AGENT}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析
    def _getlist(self, html):
        out, seen = [], set()
        for m in re.finditer(r'<li>(.*?)</li>', html, re.S):
            block = m.group(1)
            vm = re.search(r'href="(/vod/(\d+)/)"', block)
            if not vm:
                continue
            vid = vm.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            title = ''
            tm = re.search(r'class="tcl-img"[^>]*title="([^"]*)"', block)
            if not tm:
                tm = re.search(r'title="([^"]*)"', block)
            if tm:
                title = unescape(tm.group(1)).strip()

            pic = ''
            pm = re.search(r'data-original="([^"]+\.(?:jpg|png|jpeg))"', block, re.I)
            if pm:
                pic = self._abs(pm.group(1))

            remark = ''
            rm = re.search(r'<p class="tc_wz">([^<]*)</p>', block)
            if rm:
                remark = rm.group(1).strip()

            if not title:
                title = vid
            out.append({
                'vod_id': vm.group(1),
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
            })
        return out

    def _getlist_search(self, html):
        out, seen = [], set()
        for block in html.split('<div class="reusltbox">')[1:]:
            vm = re.search(r'href="/vod/(\d+)/"', block)
            if not vm:
                continue
            vid = vm.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            title = vid
            tm = re.search(r'<div class="result_title"><a href="/vod/\d+/"[^>]*>([^<]*)</a>', block)
            if tm:
                title = unescape(tm.group(1)).strip()

            pic = ''
            pm = re.search(r'data-original="([^"]+)"', block)
            if pm:
                pic = self._abs(pm.group(1))

            remark = ''
            ym = re.search(r'\((\d{4})\)', block)
            typm = re.search(r'\[([^\]]+)\]', block)
            remark = ' '.join([x for x in [ym.group(1) if ym else '', typm.group(1) if typm else ''] if x])

            out.append({
                'vod_id': '/vod/' + vid + '/',
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
            })
        return out

    def _parse_detail(self, vid_path, raw):
        # 标题
        name = ''
        tm = re.search(r'<h1[^>]*>(.*?)</h1>', raw, re.S)
        if tm:
            name = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        if not name:
            tm = re.search(r'<title>(.*?)</title>', raw, re.S)
            if tm:
                name = unescape(tm.group(1)).strip().split(' - ')[0].strip()

        # 海报
        pic = ''
        pm = re.search(r'data-original="(/upload/vod/[^"]+)"', raw)
        if pm:
            pic = self._abs(pm.group(1))

        # 简介
        desc = ''
        cm = re.search(r'<div id="content">(.*?)</div>', raw, re.S)
        if cm:
            desc = re.sub(r'<[^>]+>', ' ', cm.group(1))
            desc = re.sub(r'\s+', ' ', desc).strip()

        # 播放源：tab 标签 + 对应剧集
        play_from, play_url = self._parse_playlist(raw)

        return {
            'vod_id': vid_path,
            'vod_name': name or vid_path,
            'vod_pic': pic,
            'vod_content': desc or name or '',
            'vod_remarks': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }

    def _parse_playlist(self, raw):
        sources = []
        for tm in re.finditer(r'switch="(tab_con_playlist_\d+)"', raw):
            tab_id = tm.group(1)
            # 标签文字
            seg = raw[tm.start(): tm.start() + 600]
            label = tab_id
            lm = re.search(r'>([^<]+)</a>', seg)
            if lm:
                label = unescape(lm.group(1)).strip()

            # 该 tab 对应内容块（到下一个 tab-content 之前）
            ci = raw.find(f'id="{tab_id}"', tm.start())
            if ci < 0:
                continue
            nxt = raw.find('<div class="tab-content"', ci + 1)
            seg2 = raw[ci: nxt if nxt > 0 else ci + 30000]

            eps = []
            for em in re.finditer(r'<a href="(/yun/[^"]+)"[^>]*title="([^"]*)"', seg2):
                ep_name = unescape(em.group(2)).strip() or ('第%d集' % (len(eps) + 1))
                eps.append((ep_name, self.host + em.group(1)))

            if eps:
                sources.append((label, eps))

        if not sources:
            return '', ''

        play_from = '$$$'.join(s[0] for s in sources)
        play_url = '$$$'.join(
            '#'.join(f'{n}${u}' for n, u in eps)
            for _, eps in sources
        )
        return play_from, play_url

    def _extract_m3u8(self, raw):
        i = raw.find('var player_aaaa')
        if i < 0:
            return ''
        j = raw.find('{', i)
        k = raw.find('</script>', j)
        if j < 0 or k < 0:
            return ''
        try:
            data = json.loads(raw[j:k].strip())
        except Exception:
            # 兼容带分号结尾
            try:
                data = json.loads(raw[j:k].strip().rstrip(';'))
            except Exception:
                return ''
        return self._decode_url(data.get('url') or '', data.get('encrypt', 0))

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

