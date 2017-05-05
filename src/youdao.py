# coding=utf-8
# Keypirinha launcher (keypirinha.com)

import json
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
    URL_YOUDAO = 'http://fanyi.youdao.com/openapi.do?keyfrom={}&key={}&type=data&doctype=json&version=1.1&q={}'

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
        word = urllib.parse.quote_plus(user_input.strip())
        try:
            # get translated version of terms
            opener = kpnet.build_urllib_opener()
            opener.addheaders = [("User-agent", self.API_USER_AGENT)]
            url = self.URL_YOUDAO.format(self._keyfrom, self._key, word)
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
        for res in results:
            suggestions.append(self.create_item(
                category=self.ITEMCAT_RESULT,
                label=res['translation'],
                short_desc=res['description'],
                target=res['translation'],
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.IGNORE,
                icon_handle=self._icon,
                data_bag=kpu.kwargs_encode(
                    word=word,
                    translation=res['translation']
                )
            ))
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
        self._key = settings.get_bool("youdao_key", "main", "1061185281")
        self._keyfrom = settings.get_bool("youdao_keyfrom", "main", "my-wox")

    def _parse_api_response(self, response):
        # http://fanyi.youdao.com/openapi.do?keyfrom=my-wox&key=1061185281&type=data&doctype=json&version=1.1&q=good
        # {
        #     "errorCode":0
        #     "query":"good",
        #     "translation":["好"], // 有道翻译
        # "basic":{ // 有道词典-基本词典
        # "phonetic":"gʊd"
        #            "uk-phonetic":"gʊd" //英式发音
        # "us-phonetic":"ɡʊd" //美式发音
        # "explains":[
        #     "好处",
        #     "好的"
        #     "好"
        # ]
        # },
        # "web":[ // 有道词典-网络释义
        # {
        #     "key":"good",
        #     "value":["良好","善","美好"]
        # },
        # {...}
        # ]
        # }
        response = response.decode(encoding="utf-8", errors="strict")
        result = json.loads(response)
        translated = []
        if 0 != result['errorCode']:
            return translated
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
                    'translation': explain['key'],
                    'description': ','.join(explain['value'])
                })
        return translated
