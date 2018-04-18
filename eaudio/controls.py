import enum


class EQS:

    NIGHTCORE = {'filter': '-vn -af "atempo=1.25,'
                           'equalizer=f=500:width_type=o:width=2:g=4,'
                           'equalizer=f=125:width_type=h:width=25:g=2,'
                           'atempo=3/4,asetrate=48000*4/3', 'colour': 0x6346a8, 'name': 'nightcore'}

    BOOST = {'filter': '-vn -af "equalizer=f=95:width_type=h:width=30:g=3,'
             'equalizer=f=187.5:width_type=h:width=62.5:g=4,'
             'equalizer=f=375:width_type=h:width=125:g=3.5,'
             'equalizer=f=1500:width_type=h:width=500:g=1.5,'
             'equalizer=f=3000:width_type=o:width=.3:g=1,'
             'equalizer=f=6000:width_type=o:width=.3:g=3,'
             'equalizer=f=12000:width_type=o:width=.3:g=3', 'colour': 0x84ffb1, 'name': 'boost'}

    ROCK = {'filter': '-vn -af "'
            'equalizer=f=64:width_type=h:width=1:g=3.5,'
            'equalizer=f=125:width_type=h:width=5:g=2.5,'
            'equalizer=f=250:width_type=h:width=5:g=2,'
            'equalizer=f=500:width_type=h:width=50:g=-2,'
            'equalizer=f=1000:width_type=h:width=50:g=-2.15,'
            'equalizer=f=4000:width_type=h:width=100:g=2.25,'
            'equalizer=f=8000:width_type=h:width=100:g=2.75,'
            'equalizer=f=16000:width_type=h:width=200:g=3.25', 'colour': 0x9b2335, 'name': 'rock'}

    FLAT = {'filter': '-vn -af "equalizer=f=64:width_type=h:width=1:g=.1', 'colour': 0xc6e3f9, 'name': 'flat'}

    CFO = 'afade=t=out:st={}:d=20'
    CFI = 'afade=t=in:st=0:d=15'


PONE_CONTROLS = {'⏯': 'rp',
                 '⏹': 'stop',
                 '⏭': 'skip',
                 '🔀': 'shuffle',
                 '🔂': 'repeat',
                 '➕': 'vol_up',
                 '➖': 'vol_down',
                 'ℹ': 'queue'}

# '🔣': 'extras'

PTWO_CONTROLS = {'\U0001F1F7': ('eq', 'rock'),
                 '\U0001F1F3': ('eq', 'nightcore'),
                 '\U0001F1E7': ('eq', 'boost'),
                 '\u0030\u20E3': ('dj mode', 0),
                 '\u0031\u20E3': ('dj mode', 1),
                 '\u0032\u20E3': ('dj mode', 2),
                 '\u0033\u20E3': ('dj mode', 3),
                 '\u0034\u20E3': ('dj mode', 4),
                 'ℹ': ('dj information', None)}


class RestrictionStatus(enum.IntEnum):
    restricted_plus = 4
    restricted = 3
    semi_restricted_plus = 2
    semi_restricted = 1
    open = 0
