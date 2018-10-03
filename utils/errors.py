import discord
from discord.ext import commands

import datetime
import traceback

import utils


__all__ = ('EvieeBaseException', 'InvalidCacheLimit', 'InvalidCommand', 'MissingCommand', 'AbstractorException',
           'ImportFailure', 'StartupFailure', 'GloballyBlocked', 'MissingInstance')


class EvieeBaseException(Exception):
    pass


class InvalidCacheLimit(EvieeBaseException):
    pass


class InvalidCommand(EvieeBaseException):
    pass


class MissingCommand(EvieeBaseException):
    pass


class AbstractorException(EvieeBaseException):
    pass


class ImportFailure(EvieeBaseException):
    pass


class StartupFailure(EvieeBaseException):
    pass


class GloballyBlocked(EvieeBaseException):
    pass


class MissingInstance(EvieeBaseException):
    pass


class ErrorHandler(metaclass=utils.MetaCog, private=True):
    """Error Handler Cog."""
    __slots__ = ('bot', 'debug', 'lru_errors', 'spam', 'counter_cmdf')

    def __init__(self, bot):
        self.bot = bot
        self.debug = False
        self.lru_errors = utils.EvieeLRU(name='Errors', limit=10)
        self.spam = commands.CooldownMapping(commands.Cooldown(4, 60, commands.BucketType.user))

        self.counter_cmdf = 0

    @property
    def invalid(self):
        return (commands.CommandNotFound, commands.BadArgument, commands.MissingRequiredArgument,
                commands.MissingPermissions)

    @property
    def webhook(self):
        config = self.bot._config

        wh_id = config.get('WH', '_id')
        wh_token = config.get('WH', '_key')
        hook = discord.Webhook.partial(id=wh_id, token=wh_token, adapter=discord.AsyncWebhookAdapter(self.bot.session))
        return hook

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.NotOwner):
            bucket = self.spam.get_bucket(ctx.message)
            retry_after = bucket.update_rate_limit()

            if not retry_after:
                return await ctx.send(f'The command {ctx.command} is an owner only command!', delete_after=20)

            if ctx.author.id in self.bot.lru_blocks:
                return

            await ctx.error(level='alert', title='Blocked - Excessive Spam',
                            info='You have been blocked for 5 minutes.', content=ctx.author.mention)

            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""INSERT INTO blocks(id, reason, start, ends) VALUES ($1, 'Spam', now(), $2)
                                          ON CONFLICT (id)
                                          DO NOTHING """,
                                       ctx.author.id, datetime.datetime.utcnow() + datetime.timedelta(minutes=5))
                    self.bot.lru_blocks[ctx.author.id] = None

        elif isinstance(error, commands.CommandOnCooldown):
            bucket = self.spam.get_bucket(ctx.message)
            retry_after = bucket.update_rate_limit()

            if not retry_after:
                return await ctx.send(f'You are on cooldown. Try again in {error.retry_after:.2f}s')

            if ctx.author.id in self.bot.lru_blocks:
                return

            await ctx.error(level='alert', title='Blocked - Excessive Spam',
                            info='You have been blocked for 5 minutes.', content=ctx.author.mention)

            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""INSERT INTO blocks(id, reason, start, ends) VALUES ($1, 'Spam', now(), $2)
                                          ON CONFLICT (id)
                                          DO NOTHING """,
                                       ctx.author.id, datetime.datetime.utcnow() + datetime.timedelta(minutes=5))
                    self.bot.lru_blocks[ctx.author.id] = None

        self.counter_cmdf += 1
        # await self.bot.pool.execute(self.bot.query.on_cmd_fail)

        error = getattr(error, 'original', error)

        if not self.debug:
            if isinstance(error, self.invalid):
                return
            if hasattr(ctx.command, 'on_error'):
                return
            elif isinstance(error, commands.NoPrivateMessage):
                try:
                    return await ctx.send_err(f'The command "{ctx.command}" can not be used in Private Messages.')
                except discord.HTTPException:
                    return

        exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))

        if not ctx.command:
            command_qualified = None
            signature = None
            cog_name = None
            checks = None
        else:
            command_qualified = ctx.command.qualified_name
            signature = ctx.command.signature
            cog_name = ctx.command.cog_name
            checks = ', '.join(c.__qualname__.split('.')[0] for c in ctx.command.checks) or None

        if len(exc) > 800:
            error_fmt = await ctx.bot.create_bin(f'Command Error: {command_qualified}\n\n{exc}')
        else:
            error_fmt = exc

        if ctx.guild:
            location = f'{ctx.guild.name}(ID: {ctx.guild.id}) || ' \
                       f'{ctx.channel.name}(ID: {ctx.channel.id})<{ctx.channel.__class__.__name__}>'
        else:
            location = f'PRIVATE: (ID: {ctx.channel.id})<{ctx.channel.__class__.__name__}>'

        fmt = f'{error.__class__.__name__} - [COMMAND] - <{command_qualified}>({cog_name})\n\n' \
              f'Author    :- {ctx.author.name}(ID: {ctx.author.id})\n' \
              f'Location  :- {location}\n' \
              f'Message   :- (ID: {ctx.message.id})\n\n' \
              f'Invocation:- Invoked with "{ctx.invoked_with}" using prefix "{ctx.prefix}"\n' \
              f'Subcommand:- Invoked subcommand [{ctx.invoked_subcommand}] || ' \
              f'Subcommand passed [{ctx.subcommand_passed}]\n\n' \
              f'Checks    :- <{checks}>\n' \
              f'Passed    :- {False if isinstance(error, commands.CheckFailure) else True}\n\n' \
              f'Signature :- {signature}\n' \
              f'Args      :- <{ctx.args[2:] or None}>\n' \
              f'Kwargs    :- <{ctx.kwargs or None}> \n\n' \
              f'Timestamps:- Message({ctx.message.created_at}) | Handler({datetime.datetime.utcnow()})\n' \
              f'Payload   :- [N/A]\n\n' \
              f'Short:\n' \
              f'{error}\n\n' \
              f'Traceback:\n{error_fmt}'

        self.lru_errors[datetime.datetime.utcnow()] = fmt
        await self.webhook.send(f'```ini\n{fmt}\n```')

    @commands.command(name='error', cls=utils.AbstractorGroup, aliases=['errors'], abstractors=['get'])
    async def error_(self, ctx):
        pass

    @error_.command(name='get')
    @commands.is_owner()
    async def get_(self, ctx, *, index: int=0):
        """Retrieve an error from cache."""
        if index + 1 > len(self.lru_errors):
            return await ctx.send(f'No error exists at index {index}.')

        key = sorted(self.lru_errors.keys)[index]
        fmt = f'```ini\nCached Errors:  [{len(self.lru_errors)}]\n' \
              f'Cache Limit  :  [{self.lru_errors.limit}]\n```\n```ini\n{self.lru_errors[key]}\n```'

        await ctx.send(fmt)

    @commands.command(name='debug', cls=utils.EvieeCommand)
    @commands.is_owner()
    async def debug_(self, ctx, *, bool_: bool):
        if not bool_:
            self.debug = False
            await ctx.send('Debug mode has been set to: `False`.')
        else:
            self.debug = True
            await ctx.send('Debug mode has been set to: `True`.')
