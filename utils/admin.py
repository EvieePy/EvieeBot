import discord
from discord.ext import commands

import asyncio
import copy
import datetime
import inspect
import io
import shlex
import subprocess
import sys
import textwrap
import time
import timeit
import traceback
import typing
from contextlib import redirect_stdout

import utils


class Admin(metaclass=utils.MetaCog, private=True):
    """Admin commands for Eviee."""

    __slots__ = ('bot', )

    def __init__(self, bot):
        self.bot = bot

        bot.add_check(self.block_check)
        bot.loop.create_task(self.block_task())

    @utils.backoff_loop()
    async def block_task(self):
        await asyncio.sleep(30)

        ret = await self.bot.pool.fetch("""SELECT id FROM blocks WHERE now() >= blocks.ends""")

        if ret:
            await self.bot.pool.execute("""DELETE FROM blocks WHERE now() >= blocks.ends""")
            for value in ret:
                del self.bot.lru_blocks[value['id']]

    async def __local_check(self, ctx):
        if ctx.author.id not in self.bot.owners:
            raise commands.NotOwner
        return True

    async def __error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send('That member could not be found.')

    async def block_check(self, ctx):
        if ctx.author.id in self.bot.owners:
            return True
        elif ctx.author.id in self.bot.lru_blocks:
            raise utils.GloballyBlocked

        ret = await self.bot.pool.fetchval("""SELECT id FROM blocks WHERE id IN ($1)""", ctx.author.id)
        if ret:
            self.bot.lru_blocks[ret] = None
            raise utils.GloballyBlocked
        else:
            return True

    @commands.command(name='load', cls=utils.EvieeCommand)
    async def cog_load(self, ctx, *, cog: str):
        """Command which Loads a Module."""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='unload', cls=utils.EvieeCommand)
    async def cog_unload(self, ctx, *, cog: str):
        """Command which Unloads a Module."""

        try:
            self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='reload', cls=utils.EvieeCommand)
    async def cog_reload(self, ctx, *, cog: str):
        """Command which Reloads a Module."""

        try:
            self.bot.unload_extension(cog)
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='block', aliases=['blocc'], cls=utils.AbstractorGroup, abstractors=['add', 'remove', 'list'],
                      invoke_without_command=True)
    async def blocks(self, ctx, target: typing.Union[discord.Member, discord.User], *,
                     when: utils.UserFriendlyTime(commands.clean_content, default='something')):
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.bot.get_command('block add'), target, when=when)

    @blocks.command(name='add')
    async def block_add(self, ctx, target: typing.Union[discord.Member, discord.User], *,
                        when: utils.UserFriendlyTime(commands.clean_content, default='something')):

        ret = await self.bot.pool.fetchval("""SELECT id FROM blocks WHERE id IN ($1)""", target.id)
        if ret:
            return await ctx.send(f'{target} is already blocked.')

        await self.bot.pool.execute("""INSERT INTO blocks(id, reason, start, ends) VALUES ($1, $2, now(), $3)
                              ON CONFLICT (id)
                              DO NOTHING """, target.id, when.arg, when.dt)

        self.bot.lru_blocks[target.id] = None

        await ctx.error(title=f'Blocked - {target}', info=f'User       : `{target}(ID: {target.id})`\n'
                                                          f'Reason  : `{when.arg}`\n'
                                                          f'Ends on : `{when.dt}`\n')

    @block_add.error
    async def block_add_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Reason is a required argument that's missing derpy.")

    @blocks.command(name='remove')
    async def block_remove(self, ctx, *, target: typing.Union[discord.Member, discord.User]):
        count = await self.bot.pool.execute("""DELETE FROM blocks WHERE id IN ($1)""", target.id)

        if count == 'DELETE 0':
            return await ctx.send(f'Could not unblock {target}. They are probably not blocked?')

        del self.bot.lru_blocks[target.id]
        await ctx.send(f'Successfully removed {target} from global blocks.')

    @blocks.command(name='list')
    async def block_list(self, ctx):
        ret = await self.bot.pool.fetch("""SELECT * FROM blocks""")

        if not ret:
            return await ctx.send('Currently no blocks to show.')

        await ctx.paginate(entries=[f'{self.bot.get_user(_["id"])} - `{_["reason"]}`' for _ in ret])

    @commands.command(name='blocks', cls=utils.EvieeCommand)
    async def blocks_list_(self, ctx):
        await ctx.invoke(self.bot.get_command('block list'))

    def cleanup_code(self, content):
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    def get_syntax_error(self, e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    @commands.command(name='eval', cls=utils.EvieeCommand)
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):

        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': ctx.bot._last_result,
            'self': self
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        code = textwrap.indent(body, '  ')
        to_compile = f'async def func():\n{code}'

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await ctx.send(self.get_syntax_error(e))

        func = env['func']

        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            fmt = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
            await ctx.message.add_reaction('heleblob2:337142426340950016')
            await ctx.send(f'```py\n{value}{fmt}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('lordheleapproves:397289205228896266')
            except discord.HTTPException:
                pass

            if ret is None:
                if value:
                    if len(value) > 1000:
                        mbin = await self.bot.create_bin(value)
                        await ctx.send(mbin)
                    else:
                        await ctx.send(f'```py\n{value}\n```')
            else:
                ctx.bot._last_result = ret
                fmt = f'{value}{ret}'

                if len(fmt) > 1000:
                    code = textwrap.dedent(fmt)
                    mbin = await self.bot.create_bin(code)
                    await ctx.send(f'**Eval was uploaded to `mystb.in`:**\n {mbin}')
                else:
                    await ctx.send(f'```py\n{fmt}\n```')

    @commands.command(name='sp', cls=utils.EvieeCommand)
    async def make_subprocess_call(self, ctx, cmd: str):
        pipe = asyncio.subprocess.PIPE
        proc = await asyncio.create_subprocess_shell(cmd, stdout=pipe, stderr=pipe, loop=asyncio.get_event_loop())

        out, err = await proc.communicate()

        if err:
            await ctx.message.add_reaction('heleblob2:337142426340950016')
            data = '\n'.join(err.decode().split('\n'))
        else:
            await ctx.message.add_reaction('lordheleapproves:397289205228896266')
            data = '\n'.join(out.decode().split('\n'))

        if len(data) > 1000:
            bin_ = await self.bot.create_bin(data)
            return await ctx.send(bin_)

        await ctx.send(f'```\n{data}\n```')

    @commands.command(name='timeit', cls=utils.EvieeCommand)
    @commands.is_owner()
    async def timeit_(self, ctx, statement, number: int=100000, setup=''):
        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            'self': self
        }
        env.update(globals())

        try:
            result = timeit.timeit(statement, number=number, setup=setup, globals=env)
        except Exception as e:
            return await ctx.send(f'**There was an error running your timeit:**\n```prolog\n{e}\n```')

        await ctx.send(f'```ini\nTimeit Results ({number}x):\n\n[Statement]\n{statement}\n\n[Result]\n{result}\n```')
