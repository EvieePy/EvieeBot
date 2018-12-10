import discord
from discord.ext import commands
import re

import utils


CMATCH = re.compile('{([^\}]+)\}')
MAPPING = {'author': ('ctx', 'author'), 'channel': ('ctx', 'channel'), 'member': ('member', )}
SECONDARY = {'author': ('name', 'nick', 'mention', 'top_role', 'id', 'roles',
                        'joined_at', 'discriminator', 'created_at', 'color', 'colour', 'avatar_url'),
             'channel': ('mention', 'name', 'id')}

SECONDARY['member'] = SECONDARY['author']


class Tags(metaclass=utils.MetaCog):
    
    def __init__(self, bot):
        self.temp = {}

    @commands.command(name='tag', cls=utils.EvieeCommandGroup)
    async def tag_(self, ctx, *, inp: str):
        data = utils.StringParser(reversed=True).process_string(inp)
        string = ' '.join(reversed(list(data.values())))
        args = []
        out = None

        for a in data.values():
            try:
                out = self.temp[string]
            except KeyError:
                string = string.replace(a, '', 1).lstrip().rstrip()
                args.append(a)
                continue
            else:
                break

        if args:
            args.reverse()

        if not out:
            return await ctx.send('Could not find a tag with that name...')

        matches = CMATCH.findall(self.temp[string])

        for i, m in enumerate(matches, 0):
            # Check for additional attributes. E.g Mention or ID
            m = m.split(':')

            try:
                other = m[1]
            except IndexError:
                other = None

            # Split makes a list... duh
            m = m[0]

            try:
                attr = MAPPING[m]
            except KeyError:
                attr = None

            print(attr)

            if not attr:
                print('No ATTR')
                if m.startswith('$'):
                    print('Startswith $')
                    try:
                        out = out.replace(m, args[int(m[1]) - 1])
                    except IndexError:
                        return await ctx.send('Error')

            elif attr[0] != 'ctx':
                if attr[0] == 'member':
                    member = await discord.ext.commands.MemberConverter().convert(ctx=ctx, argument=args[i])
                    if other and other in SECONDARY[m]:
                        attr = getattr(member, other, member)
                        out = out.replace(f'{m}:{other}', str(attr))
                    else:
                        out = out.replace(m, str(member))

            elif attr[0] == 'ctx':
                attr = getattr(ctx, attr[1])
                if other and other in SECONDARY[m]:
                    attr = getattr(attr, other, attr)
                    out = out.replace(f'{m}:{other}', str(attr))
                else:
                    out = out.replace(m, str(attr))
            else:
                continue

        out = re.sub('[{}]', '', out)
        await ctx.send(out)

    @tag_.command(name='create')
    async def create_tag(self, ctx: utils.EvieeContext, name: str, *, inp: str):
        await ctx.send(f'FOUND: {CMATCH.findall(inp)}. Saving tag in temp...')

        self.temp[name] = inp