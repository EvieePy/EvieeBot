import discord
from discord.ext import commands

import asyncio

import utils


class Moderation(metaclass=utils.MetaCog, colour=0xffd0b5, thumbnail='https://i.imgur.com/QJiga6E.png'):
    """Nothing like a good spanking! These commands should give your mods a good feeling inside.
    Most of these commands require, [Manage Sever] permissions.
    """

    def __init__(self, bot):
        self.bot = bot

    async def __local_check(self, ctx):
        if ctx.invoked_with == 'help':
            return True

        if not ctx.guild:
            raise commands.NoPrivateMessage

        return True

    async def __error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.send('This command can not be used in DMs.')
            except discord.HTTPException:
                pass

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'`{error.param.name}` is a required argument which is missing.')

    @commands.command(name='prefix', cls=utils.AbstractorGroup, abstractors=['add', 'remove', 'list'])
    async def prefix(self, ctx):
        """Prefix related commands.

        <This Group implements Base Commands>
        !Base commands are also sub commands!

        Base Commands
        ---------------
            add
            remove
            list

        Examples
        ----------
        <prefix>prefix add <custom_prefix>
        <prefix>remove prefix <custom_prefix>

            {ctx.prefix}prefix list
            {ctx.prefix}prefix remove "eviee pls "
        """

    @prefix.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_prefix(self, ctx, *, prefix: str):
        """Assign a Prefix to Eviee for use in your guild.

        Examples
        ----------
        <prefix>prefix add <custom_prefix>
        <prefix>add prefix <custom_prefix>

            {ctx.prefix}add prefix "eviee pls "
            {ctx.prefix}prefix add ?!
        """
        lru = self.bot.lru_prefix[ctx.guild.id]

        prefix = prefix.strip('"').strip("'")

        if len(prefix) > 50:
            return await ctx.error(info='The prefix can not be over 50 characters long. Please try again.')
        if prefix in lru:
            return await ctx.error(info=f'`"{prefix}"` is already an assigned prefix.')

        async with self.bot.pool.acquire() as conn:
            await conn.execute("""UPDATE guilds SET prefixes = prefixes || $1::text WHERE id IN ($2)""",
                               prefix, ctx.guild.id)

        lru.append(prefix)
        await ctx.send(f'The prefix `"{prefix}"` has successfully been added.')

    @prefix.command(name='remove')
    async def remove_prefix(self, ctx, *, prefix: str):
        """Remove a Prefix from Eviee currently being used in your guild.

        Examples
        ----------
        <prefix>prefix remove <custom_prefix>
        <prefix>remove prefix <custom_prefix>

            {ctx.prefix}remove prefix "eviee pls "
            {ctx.prefix}prefix remove ?!
        """
        lru = self.bot.lru_prefix[ctx.guild.id]

        prefix = prefix.strip('"').strip("'")

        if prefix not in lru:
            return await ctx.error(info=f'`"{prefix}"` is not currently assigned to me.')

        lru.remove(prefix)
        await self.bot.pool.execute("""UPDATE guilds SET prefixes = array_remove(prefixes, $1::text) WHERE id IN ($2)""",
                                    prefix, ctx.guild.id)

        await ctx.send(f'Successfully removed `"{prefix}"` from my assigned prefixes.')

    @prefix.command(name='list')
    async def list_prefix(self, ctx):
        """List the available prefixes for your guild.

        Examples
        ----------
        <prefix>prefix list
        <prefix>list prefix

            {ctx.prefix}prefix list
            {ctx.prefix}list prefix
        """
        await ctx.paginate(title=f'Prefixes for {ctx.guild.name}', entries=self.bot.lru_prefix[ctx.guild.id],
                           fmt='`"', footer='You may also mention me.')

    @commands.command(name='prefixes', cls=utils.EvieeCommand)
    async def _prefixes(self, ctx):
        """An alias to `prefix list`.

        Examples
        ----------
        <prefix>prefixes

            {ctx.prefix}prefixes
        """
        await ctx.paginate(title=f'Prefixes for {ctx.guild.name}', entries=self.bot.lru_prefix[ctx.guild.id],
                           fmt='`"', footer='You may also mention me.')

    @commands.command(name='ban', cls=utils.EvieeCommand)
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def do_ban(self, ctx, member: discord.Member, *, reason: str=None):
        """Ban a member from your guild.

        Parameters
        ------------
        member: [Required]
            The member you wish to ban. This could be either a name, mention or ID.

        reason: str [Optional]
            Provide a reason for banning the member.

        Examples
        ----------
        <prefix>ban <member> <reason>

            {ctx.prefix}ban Noob For being a noob.
            {ctx.prefix}ban @Noob
        """
        dn = str(member)

        try:
            await ctx.guild.ban(member, reason=reason)
        except discord.HTTPException:
            return await ctx.send(f'Banning `{dn}` has failed. Please try again.')

        await ctx.send(f'Successfully banned: **`{dn}`**')

    @commands.command(name='softban', cls=utils.EvieeCommand, aliases=['sb'])
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def do_softban(self, ctx, member: discord.Member, *, reason: str=None):
        """Soft-Ban a member from your guild.

        Soft bans are similar to kicks, but unlike kicks, messages from the user will also be removed.

        Aliases
        ---------
            sb

        Parameters
        ------------
        member: [Required]
            The member you wish to soft-ban. This could be either a name, mention or ID.

        reason: str [Optional]
            Provide a reason for banning the member.

        Examples
        ----------
        <prefix>softban <member> <reason>

            {ctx.prefix}softban Noob For being a noob.
            {ctx.prefix}sb @Noob
        """
        dn = str(member)

        try:
            await ctx.guild.ban(member, reason=reason)
            await asyncio.sleep(1)
            await ctx.guild.unban(member, reason=f'Softban - {str(ctx.author)}')
        except discord.HTTPException:
            return await ctx.send(f'Soft-Banning `{dn}` has failed. Please try again.')

        await ctx.send(f'Successfully Soft-Banned: **`{dn}`**', delete_after=10)

    @commands.command(name='cleanup', cls=utils.EvieeCommand)
    @commands.has_permissions(manage_messages=True)
    async def do_cleanup(self, ctx, limit: int=20):
        """Cleanup a bot sessions messages.

        !Manage Messages is required to run this command fully!

        Parameters
        ------------
        limit: int [Optional]
            The max amount of messages to try and clean. This defaults to 20.

        Examples
        ----------
        <prefix>cleanup <limit>

            {ctx.prefix}cleanup 30
            {ctx.prefix}cleanup
        """
        messages = []
        perms = await ctx.hasperms(member=ctx.guild.me, manage_messages=True)
        controllers = [e.controller_message.id for e in self.bot.get_cog('Music').queues.values()]

        async for message in ctx.channel.history(limit=limit):
            if message.id in controllers:
                continue
            if message.content.startswith(ctx.prefix) and perms:
                messages.append(message)
            elif message.author == ctx.guild.me:
                messages.append(message)

        if not messages:
            return await ctx.send('No messages to delete...')

        if not perms:
            for i, m in enumerate(messages):
                if i == 10:
                    break
                await m.delete()
        else:
            await ctx.channel.delete_messages(messages)

        botm = len([m for m in messages if m.author == ctx.guild.me])
        userm = len(messages) - botm

        embed = discord.Embed(title='Cleanup',
                              description=f'Removed **{len(messages)}** messages successfully.',
                              colour=0xffd4d4)
        if not perms:
            embed.add_field(name='Missing Permissions', value='Could not delete any user messages due to missing'
                                                              ' **Manage Messages** permissions.')
        embed.set_footer(text=f'User Messages - {userm} | Bot Messages - {botm}')

        await ctx.send(embed=embed, delete_after=30)

    @do_cleanup.error
    async def do_cleanup_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('Manage Messages is required to run this command.')

    @do_ban.error
    @do_softban.error
    async def do_ban_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(f'{error}')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('Ban Members is required to run this command.')
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send('I require the Ban Members permission.')

    async def on_guild_join(self, guild):
        chan = self.bot.get_channel(486156641566457856)
        await chan.send(f'❤ - **{guild.name}**({guild.id}) | Members: {guild.member_count}')

    async def on_guild_remove(self, guild):
        chan = self.bot.get_channel(486156641566457856)
        await chan.send(f'💔 - **{guild.name}**({guild.id}) | Members: {guild.member_count}')
