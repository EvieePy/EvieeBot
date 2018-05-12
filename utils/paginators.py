"""The MIT License (MIT)

Copyright (c) 2018 EvieePy

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import discord

import asyncio
import inspect

import utils


async def pager(entries, chunk: int):
    for x in range(0, len(entries), chunk):
        yield entries[x:x + chunk]


class EvieeBed(discord.Embed):

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class SimplePaginator:

    __slots__ = ('entries', 'extras', 'title', 'description', 'colour', 'footer', 'length', 'prepend', 'append',
                 'fmt', 'timeout', 'ordered', 'controls', 'controller', 'pages', 'current', 'previous', 'eof', 'base',
                 'names')

    def __init__(self, **kwargs):
        self.entries = kwargs.get('entries', None)
        self.extras = kwargs.get('extras', None)

        self.title = kwargs.get('title', None)
        self.description = kwargs.get('description', None)
        self.colour = kwargs.get('colour', 0xffd4d4)
        self.footer = kwargs.get('footer', None)

        self.length = kwargs.get('length', 10)
        self.prepend = kwargs.get('prepend', '')
        self.append = kwargs.get('append', '')
        self.fmt = kwargs.get('fmt', '')
        self.timeout = kwargs.get('timeout', 90)
        self.ordered = kwargs.get('ordered', False)

        self.controller = None
        self.pages = []
        self.names = []
        self.base = None

        self.current = 0
        self.previous = 0
        self.eof = 0

        self.controls = {'⏮': 0.0, '◀': -1, '⏹': 'stop',
                         '▶': +1, '⏭': None}

    async def indexer(self, ctx, ctrl):
        if ctrl == 'stop':
            ctx.bot.loop.create_task(self.stop_controller(self.base))

        elif isinstance(ctrl, int):
            self.current += ctrl
            if self.current > self.eof or self.current < 0:
                self.current -= ctrl
        else:
            self.current = int(ctrl)

    async def reaction_controller(self, ctx):
        bot = ctx.bot
        author = ctx.author

        self.base = await ctx.send(embed=self.pages[0])

        if len(self.pages) == 1:
            await self.base.add_reaction('⏹')
        else:
            for reaction in self.controls:
                try:
                    await self.base.add_reaction(reaction)
                except discord.HTTPException:
                    return

        def check(r, u):
            if str(r) not in self.controls.keys():
                return False
            elif u.id == bot.user.id or r.message.id != self.base.id:
                return False
            elif u.id != author.id:
                return False
            return True

        while True:
            try:
                react, user = await bot.wait_for('reaction_add', check=check, timeout=self.timeout)
            except asyncio.TimeoutError:
                return ctx.bot.loop.create_task(self.stop_controller(self.base))

            control = self.controls.get(str(react))

            try:
                await self.base.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            self.previous = self.current
            await self.indexer(ctx, control)

            if self.previous == self.current:
                continue

            try:
                await self.base.edit(embed=self.pages[self.current])
            except KeyError:
                pass

    async def stop_controller(self, message):
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        try:
            self.controller.cancel()
        except Exception:
            pass

    def formmater(self, chunk):
        return '\n'.join(f'{self.prepend}{self.fmt}{value}{self.fmt[::-1]}{self.append}' for value in chunk)

    async def paginate(self, ctx):
        if self.extras:
            self.pages = [p for p in self.extras if isinstance(p, discord.Embed)]

        if self.entries:
            chunks = [c async for c in pager(self.entries, self.length)]

            for index, chunk in enumerate(chunks):
                page = discord.Embed(title=f'{self.title} - {index + 1}/{len(chunks)}', color=self.colour)
                page.description = self.formmater(chunk)

                if self.footer:
                    page.set_footer(text=self.footer)
                self.pages.append(page)

        if not self.pages:
            raise utils.EvieeBaseException('There must be enough data to create at least 1 page for pagination.')

        self.eof = float(len(self.pages) - 1)
        self.controls['⏭'] = self.eof
        self.controller = ctx.bot.loop.create_task(self.reaction_controller(ctx))


class HelpPaginator(SimplePaginator):

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controls['🔢'] = 'selector'
        self.timeout = 180

    @property
    def invalid_cogs(self):
        return 'AbstractorCommands'

    def get_embed(self, name, cog):
        embed = discord.Embed(title=f'{name} - Help',
                              description=f'```ini\n{inspect.cleandoc(cog.__doc__ or "N/A")}\n```',
                              colour=cog.colour)
        embed.set_thumbnail(url=cog.thumbnail)
        return embed

    def set_pages(self):
        length = len(self.pages)

        for index, embed in enumerate(self.pages):
            embed.set_footer(text=f'Page {index + 1}/{length} | Base commands are displayed in < >')

        for index, name in enumerate(self.names):
            self.names[index] = f'{index + 1} - `{name}`'

    async def del_msg(self, *args):
        for msg in args:
            try:
                await msg.delete()
            except discord.HTTPException:
                return

    async def wait_for(self, ctx):
        def check(m):
            return m.author == ctx.author

        msg = await ctx.send('What page would you like to goto?:')

        while True:
            try:
                resp = await ctx.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                return await self.del_msg(msg)

            try:
                index = int(resp.content)
            except ValueError:
                await ctx.send('Invalid number, please enter a valid page number.', delete_after=10)
                return await self.del_msg(resp)

            if index > len(self.pages) or index < 1:
                await ctx.send('Invalid number, please enter a valid page number.', delete_after=10)
                return await self.del_msg(resp)
            else:
                await self.del_msg(msg, resp)
                self.previous = self.current
                self.current = index - 1
                try:
                    return await self.base.edit(embed=self.pages[self.current])
                except KeyError:
                    pass

    async def indexer(self, ctx, ctrl):
        if ctrl == 'stop':
            ctx.bot.loop.create_task(self.stop_controller(self.base))
        elif ctrl == 'selector':
            ctx.bot.loop.create_task(self.wait_for(ctx))
        elif isinstance(ctrl, int):
            self.current += ctrl
            if self.current > self.eof or self.current < 0:
                self.current -= ctrl
        else:
            self.current = int(ctrl)

    async def command_formatter(self, ctx, _cog):
        cog = ctx.bot.get_cog(_cog)

        if not cog or cog.private:
            return

        embed = self.get_embed(_cog, cog)
        self.names.append(_cog)

        for index, command in enumerate(sorted(ctx.bot.get_cog_commands(_cog), key=lambda c: c.name)):
            if command.hidden:
                continue

            try:
                await command.can_run(ctx)
            except Exception:
                continue

            short = inspect.cleandoc(command.short_doc) if command.short_doc else 'No help!'

            if (index + 1) % 8 == 0:
                self.pages.append(embed)
                embed = self.get_embed(_cog, cog)
                self.names.append(_cog)

            if isinstance(command, utils.AbstractorGroup):
                abstractors = ', '.join(sorted(command.abstractors))
            else:
                abstractors = None

            if isinstance(command, utils.EvieeCommandGroup):
                subs = '\n'.join([f'    `{s}`' for s in sorted(command.commands, key=lambda _:_.name)])
                embed.add_field(name=f'{command.name} - [Group]'
                                     f'{"<{}>".format(abstractors) if abstractors else ""}',
                                value=f'{short}\n{subs}\n', inline=False)
            else:
                embed.add_field(name=command.name, value=short, inline=False)
        self.pages.append(embed)

    async def paginate(self, ctx):
        valid_cogs = [cog for cog in ctx.bot.cogs if ctx.bot.get_cog_commands(cog) and cog not in self.invalid_cogs]

        first = discord.Embed(title='Eviee - Help', description=
                                    'For more help and resources visit:\n\n'
                                    '[Official Server](http://discord.gg/Hw7RTtr)\n\n', colour=0xffb2b2)

        howto = discord.Embed(title='Help - How-to',
                              description='⏮ - `To beginning`:\n'
                                          '◀ - `Page left`:\n'
                                          '⏹ - `Close`:\n'
                                          '▶ - `Page right`:\n'
                                          '⏭ - `To End`:\n'
                                          '🔢 - `Page Selector`:\n\n',
                              colour=0xffb2b2)
        howto.add_field(name='Additional Info:', value='For additional info on how to use a specific command,'
                                                       ' use:\n\n'
                                                       '`help <command>` (Without the `<>`).\n\n'
                                                       'This may be used on all commands or their sub commands.\n\n',)

        basecom = discord.Embed(title='Help - Base Commands',
                                description='Eviee implements a command system which aims to be as human '
                                            'friendly as possible, called: `Base Commands`\n\n'
                                            'Base Commands will show up in the help like this:\n\n'
                                            '**command - [Group]<base commands>**\n'
                                            'For example:\n'
                                            '`prefix - [Group]<add, remove, reset>`\n\n'
                                            'This for example allows prefix add to be used in the'
                                            ' following ways:\n\n'
                                            f'`{ctx.prefix}prefix add ...` **or**\n'
                                            f'`{ctx.prefix}add prefix ...`',
                                colour=0xffb2b2)

        first.set_thumbnail(url=ctx.bot.user.avatar_url)
        basecom.set_thumbnail(url='https://i.imgur.com/E0ewLAN.png')
        howto.set_thumbnail(url='https://i.imgur.com/QwvPYWr.png')

        self.pages.extend((first, howto, basecom))
        self.names.extend(('Intro', 'Howto', 'Base Commands'))

        for cog in sorted(valid_cogs):
            await self.command_formatter(ctx, cog)

        self.set_pages()
        cats = [c async for c in pager(self.names, int(len(self.names) / 2))]

        for n in cats:
            joined = '\n'.join(n)
            self.pages[0].add_field(name='\u200b', value=joined)

        self.pages[0].add_field(name='\u200b',
                                value=f'Only commands which are valid for {ctx.author.mention} will be shown.\n')

        self.eof = float(len(self.pages) - 1)
        self.controls['⏭'] = self.eof
        self.controller = ctx.bot.loop.create_task(self.reaction_controller(ctx))


class ProfilePaginator(SimplePaginator):

    __slots__ = ('member', 'grabbed')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controls['📷'] = 'avatar'

        self.member = kwargs.get('member')
        self.grabbed = False

    async def indexer(self, ctx, ctrl):
        if ctrl == 'stop':
            ctx.bot.loop.create_task(self.stop_controller(self.base))
        elif ctrl == 'avatar':
            if not self.grabbed:
                self.grabbed = True
                await ctx.send(self.member.avatar_url)

        elif isinstance(ctrl, int):
            self.current += ctrl
            if self.current > self.eof or self.current < 0:
                self.current -= ctrl
        else:
            self.current = int(ctrl)


class EmojiPaginator(SimplePaginator):

    __slots__ = ('chunks', )

    def __init__(self, **kwargs):
        self.chunks = kwargs.get('chunks')
        super().__init__(**kwargs)

    async def paginate(self, ctx):
        for index, chunk in enumerate(self.chunks):
            if index % 2 == 0:
                page = discord.Embed(color=self.colour)
                page.add_field(name='\u200b', value='\n'.join(f'{e} | [{e.name}]({e.url})' for e in chunk))
                self.pages.append(page)
            else:
                page.add_field(name='\u200b', value='\n'.join(f'{e} | [{e.name}]({e.url})' for e in chunk))

        for index, page in enumerate(self.pages, 1):
            page.title = f'{self.title} - {index}/{len(self.pages)}'

        self.eof = float(len(self.pages) - 1)
        self.controls['⏭'] = self.eof
        self.controller = ctx.bot.loop.create_task(self.reaction_controller(ctx))