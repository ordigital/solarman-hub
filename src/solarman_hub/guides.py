"""Localized guides with stable, language-independent chapter identifiers."""
from importlib.resources import files
import re
from markdown_it import MarkdownIt

LANGUAGES=('en','pl','de','fr','cs','sk','lt','uk','ru')
CHAPTERS=('hub','install','cloud','history','devices','spoofing','esp32','export','ota','operations')


def render_guide(language):
    if language not in LANGUAGES:
        raise ValueError('Unsupported guide language')
    source=files('solarman_hub').joinpath('guides',language+'.md').read_text()
    renderer=MarkdownIt('commonmark',{'html':False}).enable('table')
    tokens=renderer.parse(source)
    toc=[]
    for index,token in enumerate(tokens):
        if token.type!='heading_open' or token.tag!='h2':
            continue
        inline=tokens[index+1]
        match=re.fullmatch(r'\[([a-z0-9-]+)\]\s+(.+)',inline.content)
        if not match:
            raise ValueError('Guide chapter has no stable identifier')
        chapter,title=match.groups()
        token.attrSet('id','guide-'+chapter)
        inline.content=title
        inline.children=renderer.parseInline(title)[0].children
        toc.append({'id':chapter,'title':title})
    if tuple(chapter['id'] for chapter in toc)!=CHAPTERS:
        raise ValueError('Guide chapters are incomplete or out of order')
    return {'language':language,'toc':toc,'html':renderer.renderer.render(tokens,renderer.options,{})}
