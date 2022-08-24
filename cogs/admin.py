from __future__ import annotations

from typing import Literal, TYPE_CHECKING

import os
import discord
import datetime
from discord import app_commands, Interaction, ui
from discord.ext import commands
from utils.valorant.local import ResponseLanguage
from bot import bot_option
from utils.valorant.useful import JSON

clocal = ResponseLanguage("", JSON.read("config", dir="config").get("command-description-language", "en-US"))

if TYPE_CHECKING:
    from bot import ValorantBot


class Admin(commands.Cog):
    """Error handler"""
    
    def __init__(self, bot: ValorantBot) -> None:
        self.bot: ValorantBot = bot
    
    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, sync_type: Literal['guild', 'global']) -> None:
        """ Sync the application commands """

        async with ctx.typing():
            if sync_type == 'guild':
                self.bot.tree.copy_global_to(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                await ctx.reply(f"Synced guild !")
                return

            await self.bot.tree.sync()
            await ctx.reply(f"Synced global !")
    
    @commands.command()
    @commands.is_owner()
    async def unsync(self, ctx: commands.Context, unsync_type: Literal['guild', 'global']) -> None:
        """ Unsync the application commands """
        
        async with ctx.typing():
            if unsync_type == 'guild':
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                await ctx.reply(f"Un-Synced guild !")
                return
            
            self.bot.tree.clear_commands()
            await self.bot.tree.sync()
            await ctx.reply(f"Un-Synced global !")
    
    @app_commands.command(description=clocal.get("about", {}).get("DESCRIPTION", ""))
    async def about(self, interaction: Interaction) -> None:
        """ Shows basic information about the bot. """
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        owner_url = f"https://discord.com/users/{os.getenv('OWNER_ID')}"
        titles = [response.get("FIELD1")["TITLE"], response.get("FIELD2")["TITLE"], response.get("FIELD3")["TITLE"]]
        
        embed = discord.Embed(color=0xffffff)
        bot_version = bot_option["version"]
        embed.set_footer(text = f"Version: {bot_version}")
        embed.set_author(name=response.get("TITLE"), url=response.get("PROJECT_URL"))
        embed.set_thumbnail(url=self.bot.user.avatar)
        if len(titles[0])>0:
            embed.add_field(name=titles[0], value=response.get("FIELD1")["RESPONSE"], inline=False)
        if len(titles[1])>0:
            embed.add_field(name=titles[1], value=response.get("FIELD2")["RESPONSE"], inline=False)
        if len(titles[2])>0:
            embed.add_field(name=titles[2], value=response.get("FIELD2")["RESPONSE"], inline=False)
        view = ui.View()
        view.add_item(ui.Button(label='PROJECT', url=response.get("PROJECT_URL"), row=0))
        view.add_item(ui.Button(label='BOT OWNER', url=owner_url, row=0))
        view.add_item(ui.Button(label="SUPPORT", url="https://discord.gg/FJSXPqQZgz"))
        
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: ValorantBot) -> None:
    await bot.add_cog(Admin(bot))
