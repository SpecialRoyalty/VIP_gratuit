PHRASES = [
    'meilleure groupe : {link}',
    'très bon groupe : {link}',
    'mon groupe préféré : {link}',
    'groupe à découvrir : {link}',
    'super groupe ici : {link}',
    'je recommande ce groupe : {link}',
    'meilleur groupe du moment : {link}',
    'groupe vraiment intéressant : {link}',
    'une très bonne découverte : {link}',
    'excellent groupe à rejoindre : {link}',
]


def spaced_link(link: str) -> str:
    return link.replace('https://t.me/', 'https:// t. me/', 1)


def publication_text(index: int, link: str) -> str:
    return PHRASES[index % len(PHRASES)].format(link=spaced_link(link))
