# coding=utf-8
# Keypirinha launcher (keypirinha.com)

import json
import hashlib
import random
import traceback
import urllib.error
import urllib.parse

import keypirinha as kp
import keypirinha_net as kpnet
import keypirinha_util as kpu


class youdao(kp.Plugin):
    """
    有道词典翻译插件
    """
    ACTION_DEFAULT = '0_copy'
    API_USER_AGENT = "Mozilla/5.0"
    URL_YOUDAO = 'http://openapi.youdao.com/api?q={}&from=auto&to=auto&appKey=082d2d8ef2343b9e&salt={}&sign={}'

    ITEMCAT_TRANSLATE = kp.ItemCategory.USER_BASE + 1
    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 2

    _icon = None
    _key = None
    _keyfrom = None

    def __init__(self):
        super().__init__()

    def __del__(self):
        self._clean_icon()

    def on_start(self):
        self._read_config()

        self._clean_icon()
        self._init_icon()

        self._init_actions()

    def on_catalog(self):
        self._read_config()

        self.set_catalog([self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label='yd',
            short_desc='有道翻译',
            target='yd',
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS,
            icon_handle=self._icon
        )])

    def get_md5(self, dest):
        md5 = hashlib.md5()
        md5.update(dest.encode('utf-8'))
        return md5.hexdigest().upper()

    def on_suggest(self, user_input, items_chain):
        if not user_input:
            return
        if not items_chain:
            return

        initial_item = items_chain[0]

        if self.should_terminate(0.25):
            return
        if initial_item.category() != kp.ItemCategory.KEYWORD:
            return

        suggestions = []
        origin_word = user_input.strip()
        word = urllib.parse.quote_plus(origin_word)
        try:
            # get translated version of terms
            opener = kpnet.build_urllib_opener()
            opener.addheaders = [("User-agent", self.API_USER_AGENT)]
            rnum = str(random.randint(0, 10000))
            sign = self.get_md5(self._key + origin_word + rnum + self._keyfrom)
            url = self.URL_YOUDAO.format(word, rnum, sign)
            print(url)
            with opener.open(url) as conn:
                response = conn.read()
            if self.should_terminate():
                return
            results = self._parse_api_response(response)
        except urllib.error.HTTPError as exc:
            suggestions.append(self.create_error_item(label=user_input, short_desc=str(exc)))
            return
        except Exception as exc:
            suggestions.append(self.create_error_item(label=user_input, short_desc="Error: " + str(exc)))
            traceback.print_exc()
            return
        idx = 0
        for res in results:
            suggestions.append(self.create_item(
                category=self.ITEMCAT_RESULT,
                label=str(res['translation']),
                short_desc=str(res['description']),
                target=str(idx) + str(res['translation']),
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.IGNORE,
                icon_handle=self._icon,
                data_bag=kpu.kwargs_encode(
                    word=word,
                    translation=res['translation']
                )
            ))
            idx += 1
        if suggestions:
            self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if not item and item.category() != self.ITEMCAT_RESULT:
            return
        if not item.data_bag():
            return

        data_bag = kpu.kwargs_decode(item.data_bag())
        if not action or action.name() == self.ACTION_DEFAULT:
            kpu.set_clipboard(data_bag['translation'])

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self.on_catalog()

    def _clean_icon(self):
        if self._icon:
            self._icon.free()

    def _init_icon(self):
        self._icon = self.load_icon('res://youdao/icon.png')

    def _init_actions(self):
        self.set_actions(self.ITEMCAT_TRANSLATE, [
            self.create_action(
                name=self.ACTION_DEFAULT,
                label='复制到剪切板',
                short_desc='将选择的翻译文本复制到剪切板。'
            )
        ])

    def _read_config(self):
        settings = self.load_settings()
        self._key = settings.get_bool("youdao_key", "main", "082d2d8ef2343b9e")
        self._keyfrom = settings.get_bool("youdao_keyfrom", "main", "mcv5q7AflHFZQAaN6VF43lf55aISJoq5")

    def _parse_api_response(self, response):
        response = response.decode(encoding="utf-8", errors="strict")
        result = json.loads(response)
        # {'web': [{'value': ['好', '善', '商品'], 'key': 'Good'}, {'value': ['公共物品', '公益事业', '公共财'], 'key': 'public good'}, {'value': ['干的出色', '干得好', '好工作'], 'key': 'Good Job'}],
        # 'query': 'good',
        # 'translation': ['很好'],
        # 'errorCode': '0',
        # 'basic': {'us-phonetic': 'ɡʊd', 'phonetic': 'gʊd', 'uk-phonetic': 'gʊd', 'explains': ['n. 好处；善行；慷慨的行为', 'adj. 好的；优良的；愉快的；虔诚的', 'adv. 好', 'n. (Good)人名；(英)古德；(瑞典)戈德']},
        # 'l': 'EN2zh-CHS'}
        translated = []
        if '0' != result['errorCode']:
            return translated
        if 'translation' in result.keys():
            translated.append({
                'translation': ','.join(result['translation']),
                'description': result['query']
            })
        if 'basic' in result.keys():
            basic = result['basic']
            description = ''
            if 'phonetic' in basic.keys():
                description = '音标：[' + basic['phonetic'] + '] '
            if 'uk-phonetic' in basic.keys():
                description += '英：[' + basic['uk-phonetic'] + '] '
            if 'us-phonetic' in basic.keys():
                description += '美：[' + basic['us-phonetic'] + '] '

            for explain in basic['explains']:
                translated.append({
                    'translation': explain,
                    'description': description
                })
        if 'web' in result.keys():
            for explain in result['web']:
                translated.append({
                    'translation': ','.join(explain['value']),
                    'description': explain['key']
                })
        return translated
