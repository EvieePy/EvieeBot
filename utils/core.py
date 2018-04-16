"""The MIT License (MIT)

Copyright (c) 2015-2018 Rapptz
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
from discord.backoff import ExponentialBackoff
from discord.ext import commands
from discord.ext.commands.core import hooked_wrapped_callback

import asyncio
import datetime
import inspect
import sys
import traceback
from collections import OrderedDict

import utils

__all__ = ('EvieeContext', 'EvieeCommand', 'EvieeCommandGroup', 'AbstractorGroup', 'AbstractorCommand', 'Union',
           'evieeloads', 'backoff_loop', 'get_dict', 'GuildConverter', 'MetaCog')


def get_dict(obj):
    return {obj.__class__.__name__: {k: v for (k, v) in inspect.getmembers(obj)
                                     if not k.startswith('__') and not inspect.ismethod(v)}}


class MetaCog(type):

    @classmethod
    def __prepare__(mcs, name, bases, **kwds):
        return OrderedDict()

    def __call__(cls, *args, **kwargs):
        self = super().__call__(*args, **kwargs)

        if not isinstance(args[0], commands.Bot):
            raise utils.MissingInstance('Bot is required as the first argument in MetaCogs.')

        bot = args[0]
        bot.cogs[type(self).__name__] = self

        # Add cog names to a category dict
        if self.category not in bot.categories:
            bot.categories[self.category] = []

        bot.categories[self.category].append(self)

        try:
            check = getattr(self, '_{.__class__.__name__}__global_check'.format(self))
        except AttributeError:
            pass
        else:
            bot.add_check(check)

        try:
            check = getattr(self, '_{.__class__.__name__}__global_check_once'.format(self))
        except AttributeError:
            pass
        else:
            self.add_check(check, call_once=True)

        members = inspect.getmembers(self)
        for name, member in members:
            # register commands the cog has
            if isinstance(member, commands.Command):
                if member.parent:
                    continue

                if self.private:
                    member.hidden = True

                bot.add_command(member)
                self.commands.append(member)

            # register event listeners the cog has
            elif name.startswith('on_'):
                bot.add_listener(member, name)
                self.events.append(name)

        return self

    def __new__(mcs, name, bases, namespace, **kwds):
        result = super().__new__(mcs, name, bases, namespace)

        result.colour = kwds.pop('colour', 0xff69b2)
        result.thumbnail = kwds.pop('thumbnail', 'http://pngimages.net/sites/default/files/help-png-image-34233.png')
        result.category = kwds.pop('category', None)
        result.private = kwds.pop('private', False)

        for k, v in kwds.items():
            setattr(result, k, v)

        result.commands = []
        result.events = []

        return result


class EvieeContext(commands.Context):

    def __init__(self, **attrs):
        self.colours = {'warn': 0xFFCC00, 'alert': 0xF31431}
        super().__init__(**attrs)

    async def paginate(self, **kwargs):
        cls = utils.SimplePaginator(**kwargs)
        self.bot.loop.create_task(cls.paginate(self))

    async def error(self, *, level: str='warn', title: str=None, info: str=None, content=None):
        embed = discord.Embed(title=title, description=info, colour=self.colours.get(level))
        await self.channel.send(content=content, embed=embed)

    async def invoke_sub(self, *args, **kwargs):
        if self.subcommand_passed:
            command = self.bot.get_command(f'{self.command} {self.subcommand_passed}')

            if not command:
                raise commands.CommandNotFound(f'The command {self.command} {self.subcommand_passed} was not found.')

            return await command.invoke(self, *args, **kwargs)

    async def delete_supress(self, msg: discord.Message=None):
        if not msg:
            msg = self.message

        try:
            await msg.delete()
        except discord.HTTPException:
            pass

    async def hasperms(self, *, member=None, **perms):
        if member is None:
            member = self.author

        permissions = self.channel.permissions_for(member)
        missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]

        if not missing:
            return True
        return False


class EvieeCommand(commands.Command):
    def __init__(self, name, callback, **kwargs):
        super().__init__(name=name, callback=callback, **kwargs)

    async def can_run(self, ctx):
        original = ctx.command
        ctx.command = self

        try:
            if not (await ctx.bot.can_run(ctx)):
                raise commands.CheckFailure('The global check functions for command {0.qualified_name} failed.'
                                            .format(self))

            cog = self.instance
            if cog is not None:
                try:
                    local_check = getattr(cog, '_{0.__class__.__name__}__local_check'.format(cog))
                except AttributeError:
                    pass
                else:
                    ret = await discord.utils.maybe_coroutine(local_check, ctx)
                    if not ret:
                        return False

            if ctx.author.id in ctx.bot.owners:
                return True

            predicates = self.checks
            if not predicates:
                return True

            return await discord.utils.async_all(predicate(ctx) for predicate in predicates)
        finally:
            ctx.command = original


class EvieeCommandGroup(commands.GroupMixin, EvieeCommand):
    def __init__(self, **attrs):
        self.invoke_without_command = attrs.pop('invoke_without_command', True)
        super().__init__(**attrs)

    def command(self, *args, **kwargs):
        def decorator(func):
            result = commands.command(cls=EvieeCommand, *args, **kwargs)(func)
            try:
                self.add_command(result)
            except Exception as e:
                print(e)
            return result

        return decorator

    def group(self, *args, **kwargs):
        def decorator(func):
            result = commands.group(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    async def invoke(self, ctx):
        early_invoke = not self.invoke_without_command
        if early_invoke:
            await self.prepare(ctx)

        view = ctx.view
        previous = view.index
        view.skip_ws()
        trigger = view.get_word()

        if trigger:
            ctx.subcommand_passed = trigger
            ctx.invoked_subcommand = self.all_commands.get(trigger, None)

        if early_invoke:
            injected = hooked_wrapped_callback(self, ctx, self.callback)
            await injected(*ctx.args, **ctx.kwargs)

        if trigger and ctx.invoked_subcommand:
            ctx.invoked_with = trigger
            await ctx.invoked_subcommand.invoke(ctx)
        elif not early_invoke:
            view.index = previous
            view.previous = previous
            await super().invoke(ctx)

    async def reinvoke(self, ctx, *, call_hooks=False):
        early_invoke = not self.invoke_without_command
        if early_invoke:
            ctx.command = self
            await self._parse_arguments(ctx)

            if call_hooks:
                await self.call_before_hooks(ctx)

        view = ctx.view
        previous = view.index
        view.skip_ws()
        trigger = view.get_word()

        if trigger:
            ctx.subcommand_passed = trigger
            ctx.invoked_subcommand = self.all_commands.get(trigger, None)

        if early_invoke:
            try:
                await self.callback(*ctx.args, **ctx.kwargs)
            except Exception:
                ctx.command_failed = True
                raise
            finally:
                if call_hooks:
                    await self.call_after_hooks(ctx)

        if trigger and ctx.invoked_subcommand:
            ctx.invoked_with = trigger
            await ctx.invoked_subcommand.reinvoke(ctx, call_hooks=call_hooks)
        elif not early_invoke:
            # undo the trigger parsing
            view.index = previous
            view.previous = previous
            await super().reinvoke(ctx, call_hooks=call_hooks)


class AbstractorCommand(EvieeCommand):
    def __init__(self, name, callback, **kwargs):
        super().__init__(name=name, callback=callback, **kwargs)


class AbstractorGroup(EvieeCommandGroup):
    def __init__(self, **attrs):
        super().__init__(**attrs)
        self.abstractors = set(attrs.pop('abstractors', []))


class AbstractorCommands:
    """Commands which serve as a base abstract method for all other sub-commands.

     Groups which implement abstractor commands allow them to be used in a more human friendly way.

     Examples
     ----------

        @abstractor_group(name='meme', abstractors=['get'])
        async def memes(ctx):
            # Meme commands group

        @memes.command(name='get')
        async def get_meme(ctx):
            # Get a meme

    Assuming you have an abstractor_command setup for get, calling: get meme is equiv to meme get
    """
    def __init__(self):
        pass

    @commands.command(name='add', cls=AbstractorCommand)
    async def abstractor_add(self, ctx):
        """Base Abstractor Command for add."""
        pass

    @commands.command(name='remove', cls=AbstractorCommand)
    async def abstractor_remove(self, ctx):
        """Base Abstractor Command for remove."""
        pass

    @commands.command(name='reset', cls=AbstractorCommand)
    async def abstractor_reset(self, ctx):
        """Base Abstractor Command for reset."""
        pass

    @commands.command(name='disable', cls=AbstractorCommand)
    async def abstractor_disable(self, ctx):
        """Base Abstractor Command for disable."""
        pass

    @commands.command(name='enable', cls=AbstractorCommand)
    async def abstractor_enable(self, ctx):
        """Base Abstractor Command for enable."""
        pass

    @commands.command(name='get', cls=AbstractorCommand)
    async def abstractor_get(self, ctx):
        """Base Abstractor Command for get."""
        pass

    @commands.command(name='list', cls=AbstractorCommand)
    async def abstractor_list(self, ctx):
        """Base Abstractor Command for list."""
        pass

    @commands.command(name='show', cls=AbstractorCommand)
    async def abstractor_show(self, ctx):
        """Base Abstractor Command for show."""

    @commands.command(name='new', cls=AbstractorCommand)
    async def abstractor_new(self, ctx):
        """Base Abstractor Command for new."""

    @commands.command(name='give', cls=AbstractorCommand)
    async def abstractor_give(self, ctx):
        """Base Abstractor Command for give."""

    @commands.command(name='help', hidden=True)
    async def help_paginator(self, ctx, *, entry: str = None):
        if not entry:
            helpy = utils.HelpPaginator()
            return await helpy.paginate(ctx)

        entry = entry.lower()

        command = ctx.bot.get_command(entry)
        if command is None:
            return

        docs = inspect.cleandoc(command.help)
        docs = docs.split('[S]')
        pages = []

        for index, doc in enumerate(docs):
            embed = discord.Embed(title=f'Help - {entry} | Page {index + 1}/{len(docs)}',
                                  description=f'```ini\n{doc.format(ctx=ctx)}\n```',
                                  colour=0xffb2b2)
            pages.append(embed)

        await ctx.paginate(extras=pages)


# Converters
class Union(commands.Converter):
    """Union converter."""
    def __init__(self, *converters):
        self.converters = converters

    async def convert(self, ctx, argument: str):
        for converter in self.converters:
            try:
                return await ctx.command.do_conversion(ctx, converter, argument)
            except (commands.BadArgument, ValueError, TypeError):
                pass

        converters = ", ".join(x.__name__ for x in self.converters)
        raise commands.BadArgument(f'Converting to one of {converters} failed.')


class GuildConverter(commands.IDConverter):
    """Converts to a Guild."""
    async def convert(self, ctx, argument):
        id_ = self._get_id_match(argument)

        if id_:
            result = ctx.bot.get_guild(int(id_.group(1)))
        else:
            result = discord.utils.find(lambda g: g.name == argument, ctx.bot.guilds)

        if not result:
            raise commands.BadArgument(f'Could not find a guild matching <{argument}>', argument)

        return result


# Decos
def evieeloads(func):
    """Decorator which allows timing and handling of startup methods."""
    async def wrapper(*args, **kwargs):
        started = datetime.datetime.utcnow()

        try:
            if inspect.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        except Exception:
            print(f'\n\n[CRITICAL] | Startup failure in call to function <{func.__name__}>\n', file=sys.stderr)
            traceback.print_exc()

            # Allow eviee to call shutdown
            raise utils.StartupFailure()

        ended = datetime.datetime.utcnow()
        return print(f'{func.__name__}: {ended - started}')
    return wrapper


def backoff_loop(until_ready=True):
    """Decorator which converts a task into a loop, and applies an Exponential Backoff on reconnecting state."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if isinstance(args[0], commands.Bot):
                bot = args[0]
            elif not isinstance(args[0].bot, commands.Bot):
                raise utils.MissingInstance(f'Missing an instance of Bot in task <{func.__name__}>.')
            else:
                bot = args[0].bot

            backoff = ExponentialBackoff()
            retrys = 0

            if until_ready:
                await bot.wait_until_ready()

            while not bot.is_closed():
                await func(*args, *kwargs)

                while bot.is_reconnecting():
                    retrys += 1
                    retry = backoff.delay()
                    await asyncio.sleep(retry)

                if retrys:
                    print(f'Resumed Task: {func.__name__} after {retrys} trys.\n')
                    retrys = 0
        return wrapper
    return decorator


def setup(bot):
    bot.add_cog(AbstractorCommands())

