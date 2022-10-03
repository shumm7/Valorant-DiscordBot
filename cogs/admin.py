from __future__ import annotations
from re import M

from typing import Literal, TYPE_CHECKING

import os, json
import discord
import datetime
from discord import app_commands, Interaction, ui
from discord.ext import commands
from utils.errors import ValorantBotError
from utils.checks import owner_only
from utils.valorant.embed import GetEmbed, Embed
from utils.valorant.local import ResponseLanguage
from bot import bot_option
from utils.valorant.useful import JSON, load_file
import utils.config as Config

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
        
        config = Config.LoadConfig().get("owner-id")
        owner_url = f"https://discord.com/users/{config}"
        titles = [response.get("FIELD1")["TITLE"], response.get("FIELD2")["TITLE"], response.get("FIELD3")["TITLE"]]
        
        embed = Embed()
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
    
    @app_commands.command(description=clocal.get("update", {}).get("DESCRIPTION", ""))
    async def update(self, interaction: Interaction) -> None:
        """ Shows basic information about the bot. """
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        embeds = GetEmbed.update_embed(self.bot.bot_version, self.bot)
        
        if len(embeds)>0:
            await interaction.response.send_message(embeds=embeds)
        else:
            raise ValorantBotError(response.get("ERROR"))
    
    @app_commands.command(description=clocal.get("help", {}).get("DESCRIPTION", ""))
    @app_commands.describe(command=clocal.get("help", {}).get("DESCRIBE", {}).get("command", ""))
    async def help(self, interaction: Interaction, command: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        command = command.replace("_", " ")
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        embed = Embed()

        if command == None: # WIP
            embed.title = response.get("TITLE")
            embed.description = response.get("RESPONSE")
        else:
            command_response = ResponseLanguage(command.replace(" ", "_"), interaction.locale)
            if command_response.get("NAME")==None:
                raise ValorantBotError(response.get("NOT_FOUND"))
            
            description = command_response.get("DESCRIPTION")

            describe = command_response.get("DESCRIBE")
            command_line, arguments = "", ""
            if describe!=None:
                for argument, lines in describe.items():

                    if len(command_line)>0:
                        command_line += " "
                    command_line += f"<{argument}>"

                    if len(arguments)>0:
                        arguments += "\n"
                    arguments += f"`{argument}`: {lines}"
            
            command_line = f"`/{command} {command_line}`"

            # Embed
            embed.title=command
            embed.description = f"{description}\n{command_line}"
            if len(arguments)>0:
                embed.add_field(name=response.get("ARGUMENTS"), value=arguments)
        

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(description=clocal.get("dump", {}).get("DESCRIPTION", ""))
    @app_commands.describe(data=clocal.get("dump", {}).get("DESCRIBE", {}).get("data", ""))
    @commands.is_owner()
    async def dump(self, interaction: Interaction, data: str) -> None:
        """ Dump cache.json """
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        response = ResponseLanguage(interaction.command.name, interaction.locale)
        cache = JSON.read("cache")
        raw: str
        name: str

        if data == None:
            raw = json.dumps(cache, indent=4, ensure_ascii=False)
            name = "cache.json"
        else:
            dict = cache.get(data)
            if dict:
                raw = json.dumps(dict, indent=4, ensure_ascii=False)
                name = f"{data}.json"
            else:
                raise ValorantBotError(response.get("NOT_FOUND"))

        try:
            f = open("resources/temp/cache.json", 'w', encoding="utf-8")
            f.write(raw)
            f.close()

            size = os.path.getsize("resources/temp/cache.json")
            if size > 8388608:
                raise ValorantBotError(response.get("FILESIZE_ERROR"))

            embed = Embed(response.get("RESPONSE"))
            file = load_file("resources/temp/cache.json", name)

            await interaction.response.send_message(embed=embed, file=file)
        except Exception as e:
            print(e)
            raise ValorantBotError(response.get("ERROR"))
    

async def setup(bot: ValorantBot) -> None:
    await bot.add_cog(Admin(bot))
