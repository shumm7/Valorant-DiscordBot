from __future__ import annotations

import contextlib
import datetime
import dateutil.parser
import math, os
from difflib import SequenceMatcher
from typing import Literal, TYPE_CHECKING  # noqa: F401

from discord import app_commands, Interaction, ui, File
from discord.ext import commands, tasks
from discord.utils import MISSING

from utils.checks import owner_only
from utils.errors import (
    ValorantBotError
)
from utils.valorant import cache as Cache, useful, view as View
from utils.valorant.db import DATABASE
from utils.valorant.embed import Embed, GetEmbed
from utils.valorant.endpoint import API_ENDPOINT
from utils.valorant.local import ResponseLanguage, LocalErrorResponse
from utils.valorant.resources import setup_emoji
from utils.valorant.useful import JSON, GetItems
from utils.locale_v2 import ValorantTranslator
import utils.config as Config

VLR_locale = ValorantTranslator()
clocal = ResponseLanguage("", JSON.read("config", dir="config").get("command-description-language", "en-US"))

if TYPE_CHECKING:
    from bot import ValorantBot


class ValorantCog(commands.Cog, name='Valorant'):
    """Valorant API Commands"""
    
    def __init__(self, bot: ValorantBot) -> None:
        self.bot: ValorantBot = bot
        self.endpoint: API_ENDPOINT = None
        self.db: DATABASE = None
        self.reload_cache.start()
    
    def cog_unload(self) -> None:
        self.reload_cache.cancel()
    
    def funtion_reload_cache(self, force=False) -> None:
        """ Reload the cache """
        with contextlib.suppress(Exception):
            config = Config.LoadConfig()
            cache = self.db.read_cache()
            valorant_version = Cache.get_valorant_version()
            bot_version = self.bot.bot_version
            if valorant_version != cache['valorant_version'] or (bot_version != cache["bot_version"] and config.get("reset-cache-when-updated", False)) or force:
                Cache.get_cache(bot_version)
                cache = self.db.read_cache()
                cache['bot_version'] = bot_version
                cache['valorant_version'] = valorant_version
                self.db.insert_cache(cache)
                print(f"[{datetime.datetime.now()}] *** Updated cache ***")
    
    @tasks.loop(minutes=30)
    async def reload_cache(self) -> None:
        """ Reload the cache every 30 minutes """
        self.funtion_reload_cache()
    
    @reload_cache.before_loop
    async def before_reload_cache(self) -> None:
        """ Wait for the bot to be ready before reloading the cache """
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """ When the bot is ready """
        self.db = DATABASE()
        self.endpoint = API_ENDPOINT()
    
    async def get_endpoint(self, user_id: int, locale_code: str = None, username: str = None, password: str = None) -> API_ENDPOINT:
        """ Get the endpoint for the user """
        if username is not None and password is not None:
            auth = self.db.auth
            auth.locale_code = locale_code
            data = await auth.temp_auth(username, password)
        elif username or password:
            raise ValorantBotError(f"Please provide both username and password!")
        else:
            data = await self.db.is_data(user_id, locale_code)
        data['locale_code'] = locale_code
        endpoint = self.endpoint
        endpoint.activate(data)
        return endpoint
    
    async def check_update(self, interaction: Interaction) -> None:
        db = self.db.read_db()
        user_id = interaction.user.id
        version = self.bot.bot_version
        oncemsg = LocalErrorResponse("UPDATE_NOTIFY", interaction.locale)

        try:
            if db.get(str(user_id), {}).get("update_notify", False) and db.get(str(user_id), {}).get("update") != version:
                embeds = GetEmbed.update_embed(version, self.bot)
                if len(embeds)>0:
                    await interaction.followup.send(content=oncemsg, embeds=embeds, ephemeral=True)

                    db[str(user_id)]["update"] = version
                    self.db.insert_user(db)
        except:
            print(f"[{datetime.datetime.now()}] Failed to send an update notify.")


    @app_commands.command(description=clocal.get("login", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("login", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("login", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def login(self, interaction: Interaction, username: str, password: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        user_id = interaction.user.id
        auth = self.db.auth
        auth.locale_code = interaction.locale
        authenticate = await auth.authenticate(username, password)
        
        if authenticate['auth'] == 'response':
            await interaction.response.defer(ephemeral=True)
            login = await self.db.login(user_id, authenticate, interaction.locale)
            
            if login['auth']:
                embed = Embed(response.get('SUCCESS', '').format(name=login['player']))
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            raise ValorantBotError(f"{response.get('FAILED')}")
        
        elif authenticate['auth'] == '2fa':
            cookies = authenticate['cookie']
            message = authenticate['message']
            label = authenticate['label']
            modal = View.TwoFA_UI(interaction, self.db, cookies, message, label, response)
            await interaction.response.send_modal(modal)
    
    @app_commands.command(description=clocal.get("logout", {}).get("DESCRIPTION", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def logout(self, interaction: Interaction) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")
        
        await interaction.response.defer(ephemeral=True)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        user_id = interaction.user.id
        
        view = View.Logout(interaction, user_id, self.db, response)
        await view.start()
    
    @app_commands.command(description=clocal.get("account", {}).get("DESCRIPTION", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def account(self, interaction: Interaction) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")
        
        await interaction.response.defer(ephemeral=True)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        user_id = interaction.user.id
        
        view = View.Logout(interaction, user_id, self.db, response)
        await view.start_swtich()
    
    # credit https://github.com/giorgi-o
    # https://github.com/giorgi-o/SkinPeek/wiki/How-to-get-your-Riot-cookies
    @app_commands.command(description=clocal.get("cookies", {}).get("DESCRIPTION", ""))
    @app_commands.describe(cookie=clocal.get("cookies", {}).get("DESCRIBE", {}).get("cookie", ""))
    async def cookies(self, interaction: Interaction, cookie: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        login = await self.db.cookie_login(interaction.user.id, cookie, interaction.locale)
        
        if login['auth']:
            embed = Embed(f"{response.get('SUCCESS')} **{login['player']}!**")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        view = ui.View()
        view.add_item(ui.Button(label="Tutorial", emoji="🔗", url="https://youtu.be/cFMNHEHEp2A"))
        await interaction.followup.send(f"{response.get('FAILURE')}", view=view, ephemeral=True)

    @app_commands.command(description=clocal.get("store", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("store", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("store", {}).get("DESCRIBE", {}).get("password", ""))
    # @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def store(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        # get endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # fetch skin price
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)
        
        # data
        data = endpoint.store_fetch_storefront()
        embeds = GetEmbed.store(endpoint.player, data, response, self.bot)
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("point", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("point", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("point", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def point(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.store_fetch_wallet()
        embed = GetEmbed.point(endpoint.player, data, response, self.bot)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)
        await self.check_update(interaction)

    @app_commands.command(description=clocal.get("rank", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("rank", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("rank", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def rank(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_player_mmr()
        embed = GetEmbed.rank(endpoint.player, data, response, endpoint, self.bot)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("collection", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("collection", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("collection", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def collection(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_player_inventory(endpoint.puuid)
        view = View.BaseCollection(interaction, data, endpoint, response)
        await view.start()
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("career", {}).get("DESCRIPTION", ""))
    @app_commands.describe(matches=clocal.get("career", {}).get("DESCRIBE", {}).get("matches", ""), queue=clocal.get("career", {}).get("DESCRIBE", {}).get("queue", ""), username=clocal.get("career", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("career", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def career(self, interaction: Interaction, matches: int = 1, queue: Literal['All', 'Competitive', 'Unrated', 'Deathmatch', 'Escalation', 'Replication', 'Spike Rush', 'Custom', 'Snowball Fight', 'New Map']="Competitive", username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # limit of argument "matches"
        match_limit = 8
        
        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)

        # queue
        if queue == "All":
            queue = ""
        elif queue=="Competitive":
            queue="competitive"
        elif queue=="Unrated":
            queue="unrated"
        elif queue=="Deathmatch":
            queue="deathmatch"
        elif queue=="Escalation":
            queue="ggteam"
        elif queue=="Replication":
            queue="onefa"
        elif queue=="Spike Rush":
            queue="spikerush"
        elif queue=="Custom":
            queue="custom"
        elif queue=="Snowball Fight":
            queue="snowball"
        elif queue=="newmap":
            queue="newmap"
        
        # data
        if matches<=0 or matches>match_limit:
            raise ValorantBotError(response.get('FAILED').format(limit=match_limit))
        data = endpoint.fetch_match_history(index=20, queue=queue, not_found_error=False)
        if len(data.get("Matches", [])) > matches:
            data["Matches"] = data["Matches"][:matches]
        
        embeds = GetEmbed.career(endpoint.player, endpoint.puuid, data, response, endpoint, queue, self.bot)
        
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        await self.check_update(interaction)

    @app_commands.command(description=clocal.get("match", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("match", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("match", {}).get("DESCRIBE", {}).get("password", ""), match_id=clocal.get("match", {}).get("DESCRIBE", {}).get("match_id", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def match(self, interaction: Interaction, match_id: str = "", username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage("match", interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        if len(match_id)==0:
            data = endpoint.fetch_match_history(index=1)["Matches"]
            if len(data)==1:
                match_id = data[0]["MatchID"]

        date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
        filename = [f"loadout_graph_{date}.png", f"duels_heatmap_{date}.png"]
        ret = GetEmbed.match(endpoint.player, endpoint.puuid, match_id, response, endpoint, filename, self.bot)
        embeds, graph = ret[0], ret[1]

        if graph==None:
            await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        else:
            if len(embeds)>2:
                await interaction.followup.send(embeds=embeds[:2], file=graph[0], view=View.share_button(interaction, embeds[:2]) if is_private_message else MISSING)
                await interaction.followup.send(embeds=embeds[2:4], view=View.share_button(interaction, embeds[2:4]) if is_private_message else MISSING)
                await interaction.followup.send(embeds=embeds[4:], file=graph[1], view=View.share_button(interaction, embeds[4:]) if is_private_message else MISSING)
            else:
                await interaction.followup.send(embeds=embeds, files=graph, view=View.share_button(interaction, embeds) if is_private_message else MISSING)

            try:
                os.remove("resources/temp/" + filename[0])
            except FileNotFoundError:
                pass
            try:
                os.remove("resources/temp/" + filename[1])
            except FileNotFoundError:
                pass
            await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("mission", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("mission", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("mission", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def mission(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_contracts()
        embed = GetEmbed.mission(endpoint.player, data, response)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("nightmarket", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("nightmarket", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("nightmarket", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def nightmarket(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # fetch skin price
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)
        
        # data
        data = endpoint.store_fetch_storefront()
        embeds = GetEmbed.nightmarket(endpoint.player, data, self.bot, response)
        
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("battlepass", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("battlepass", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("battlepass", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def battlepass(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        embeds = []
        embeds.append(Embed(description=response.get("RESPONSE").format(player=endpoint.player)))
        
        #data
        data = endpoint.fetch_contracts()
        content = endpoint.fetch_content()
        season = useful.get_season_by_content(content)
        events = GetItems.get_current_event()

        # battlepass
        embed = GetEmbed.battlepass(self.bot, endpoint.player, data, season, response)
        embeds.extend(embed)

        # events
        for event in events:
            embed = GetEmbed.battlepass_event(self.bot, endpoint.player, data, event, response)
            embeds.append(embed)

        
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    # inspired by https://github.com/giorgi-o
    @app_commands.command(description=clocal.get("bundle", {}).get("DESCRIPTION", ""))
    @app_commands.describe(bundle=clocal.get("bundle", {}).get("DESCRIBE", {}).get("bundle", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def bundle(self, interaction: Interaction, bundle: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # cache
        cache = self.db.read_cache()
        
        # default language language
        default_language = JSON.read("config", dir="config").get("default-language", "en-US")
        
        # find bundle
        find_bundle_en_US = [cache['bundles'][i] for i in cache['bundles'] if bundle.lower() in cache['bundles'][i]['names'][default_language].lower()]
        find_bundle_locale = [cache['bundles'][i] for i in cache['bundles'] if bundle.lower() in cache['bundles'][i]['names'][str(VLR_locale)].lower()]
        find_bundle = find_bundle_en_US if len(find_bundle_en_US) > 0 else find_bundle_locale
        
        # bundle view
        view = View.BaseBundle(interaction, find_bundle, response)
        await view.start()
        await self.check_update(interaction)
    
    # inspired by https://github.com/giorgi-o
    @app_commands.command(description=clocal.get("feature", {}).get("DESCRIPTION", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def feature(self, interaction: Interaction) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)
        
        # data
        bundle_entries = endpoint.store_fetch_storefront()
        
        # bundle view   
        view = View.BaseBundle(interaction, bundle_entries, response)
        await view.start_furture()
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("agent", {}).get("DESCRIPTION", ""))
    @app_commands.describe(agent=clocal.get("agent", {}).get("DESCRIBE", {}).get("agent", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def agent(self, interaction: Interaction, agent: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # cache
        cache = self.db.read_cache()
        
        # default language language
        default_language = JSON.read("config", dir="config").get("default-language", "en-US")
        
        
        # find agents
        find_agent_en_US = []
        find_agent_locale = []

        
        for item_key, item_agent in cache['agents'].items():
            if agent.lower() == "all":
                data = item_agent
                data["uuid"] = item_key
                find_agent_en_US.append(data)
            else:
                if agent.lower() in cache['agents'][item_key]['name'][default_language].lower():
                    data = item_agent
                    data["uuid"] = item_key
                    find_agent_en_US.append(data)
                
                if agent.lower() in cache['agents'][item_key]['name'][str(VLR_locale)].lower():
                    data = item_agent
                    data["uuid"] = item_key
                    find_agent_locale.append(data)
            
        find_agent = find_agent_en_US if len(find_agent_en_US) > 0 else find_agent_locale

        # agents view
        view = View.BaseAgent(interaction, find_agent, response)
        await view.start()
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("contract", {}).get("DESCRIPTION", ""))
    @app_commands.describe(agent=clocal.get("contract", {}).get("DESCRIBE", {}).get("agent", ""), username=clocal.get("contract", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("contract", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def contract(self, interaction: Interaction, agent: str = None, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        await interaction.response.defer(ephemeral=is_private_message)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        default_language = JSON.read("config", dir="config").get("default-language", "en-US")
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)

        # cache
        cache = self.db.read_cache()
        
        #data
        fetch_data = endpoint.fetch_contracts()
        
        # find agents
        find_agent_en_US = []
        find_agent_locale = []
        find_agent = []

        if agent == None:
            agent_uuid = cache["contracts"][fetch_data["ActiveSpecialContract"]]["reward"]["relationUuid"]
            data = cache["agents"][agent_uuid]
            data["uuid"] = agent_uuid
            find_agent = [data]
        else:
            for item_key, item_agent in cache['agents'].items():
                if agent.lower() == "all":
                    data = item_agent
                    data["uuid"] = item_key
                    find_agent_en_US.append(data)
                else:
                    if agent.lower() in cache['agents'][item_key]['name'][default_language].lower():
                        data = item_agent
                        data["uuid"] = item_key
                        find_agent_en_US.append(data)
                    
                    if agent.lower() in cache['agents'][item_key]['name'][str(VLR_locale)].lower():
                        data = item_agent
                        data["uuid"] = item_key
                        find_agent_locale.append(data)
            
            find_agent = find_agent_en_US if len(find_agent_en_US) > 0 else find_agent_locale

        # contract view
        view = View.BaseContract(interaction, find_agent, fetch_data, response, endpoint.player, endpoint, is_private_message)
        await view.start()
        await self.check_update(interaction)

    @app_commands.command(description=clocal.get("weapon", {}).get("DESCRIPTION", ""))
    @app_commands.describe(weapon=clocal.get("weapon", {}).get("DESCRIBE", {}).get("weapon", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def weapon(self, interaction: Interaction, weapon: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # cache
        cache = self.db.read_cache()
        
        # default language language
        default_language = JSON.read("config", dir="config").get("default-language", "en-US")
        
        
        # find weapon
        find_weapon_en_US = []
        find_weapon_locale = []

        
        for item_key, item_weapon in cache['weapons'].items():
            if weapon.lower() == "all":
                data = item_weapon
                data["uuid"] = item_key
                data["type"] = "weapon"
                find_weapon_en_US.append(data)
            else:
                if weapon.lower() in cache['weapons'][item_key]['names'][default_language].lower():
                    data = item_weapon
                    data["uuid"] = item_key
                    data["type"] = "weapon"
                    find_weapon_en_US.append(data)
                
                if weapon.lower() in cache['weapons'][item_key]['names'][str(VLR_locale)].lower():
                    data = item_weapon
                    data["uuid"] = item_key
                    data["type"] = "weapon"
                    find_weapon_locale.append(data)
        
        for item_key, item_gear in cache['gears'].items():
            if weapon.lower() == "all":
                data = item_gear
                data["uuid"] = item_key
                data["type"] = "gear"
                find_weapon_en_US.append(data)
            else:
                if weapon.lower() in cache['gears'][item_key]['names'][default_language].lower():
                    data = item_gear
                    data["uuid"] = item_key
                    data["type"] = "gear"
                    find_weapon_en_US.append(data)
                
                if weapon.lower() in cache['gears'][item_key]['names'][str(VLR_locale)].lower():
                    data = item_gear
                    data["uuid"] = item_key
                    data["type"] = "gear"
                    find_weapon_locale.append(data)
            
        find_weapon = find_weapon_en_US if len(find_weapon_en_US) > 0 else find_weapon_locale

        # weapon view
        view = View.BaseWeapon(interaction, find_weapon, response)
        await view.start()
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("skin", {}).get("DESCRIPTION", ""))
    @app_commands.describe(skin=clocal.get("skin", {}).get("DESCRIBE", {}).get("skin", ""), username=clocal.get("skin", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("skin", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def skin(self, interaction: Interaction, skin: str, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        await interaction.response.defer(ephemeral=is_private_message)

        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # cache
        cache = self.db.read_cache()
        
        # default language language
        default_language = JSON.read("config", dir="config").get("default-language", "en-US")

        # fetch skin price and owns
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)
        entitlements = endpoint.store_fetch_entitlements()
        
        # find skin
        find_skin_en_US = []
        find_skin_locale = []

        for item in cache['skins'].values():
            if skin.lower() in cache['skins'][item["uuid"]]['names'][default_language].lower():
                find_skin_en_US.append(item)
            
            if skin.lower() in cache['skins'][item["uuid"]]['names'][str(VLR_locale)].lower():
                find_skin_locale.append(item)
            
        find_skin = find_skin_en_US if len(find_skin_en_US) > 0 else find_skin_locale

        # skin view
        view = View.BaseSkin(interaction, find_skin[:25], response, entitlements, is_private_message)
        await view.start()
        await self.check_update(interaction)

    @app_commands.command(description=clocal.get("crosshair", {}).get("DESCRIPTION", ""))
    @app_commands.describe(code=clocal.get("crosshair", {}).get("DESCRIBE", {}).get("code", ""), name=clocal.get("crosshair", {}).get("DESCRIBE", {}).get("name", ""))
    async def crosshair(self, interaction: Interaction, code: str = "", name: str = "") -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)

        # crosshair template
        template = JSON.read("crosshair", dir="config")
        icon = ""

        if len(name)>0:
            max = 0
            selected = ""
            for data in template.values():
                for n in data["crosshairs"].keys():
                    r = SequenceMatcher(None, n.lower(), name.lower()).ratio()
                    if r>max:
                        max = r
                        selected_category = data
                        selected = n
            
            player = ""
            if selected_category.get("category")=="esports":
                player = selected_category["name"] + " - " + selected
            else:
                player = selected
            icon = selected_category["icon"]
            code = selected_category["crosshairs"][selected]
        else:
            player = endpoint.player

        if len(code)<=0:
            raise ValorantBotError(response.get("NO_CODE"))
        
        # data
        filename = f"crosshair_" + datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') +".png"
        file = endpoint.fetch_crosshair(code, filename)
        if file==None:
            raise ValorantBotError(response.get("ERROR"))
        
        # embed
        embed = Embed(title=response.get("TITLE"), description=response.get("RESPONSE").format(player=player, code=code)).set_image(url=f"attachment://{filename}")
        embed.set_thumbnail(url=icon)
        await interaction.followup.send(embed=embed, file=file)
        await self.check_update(interaction)
        os.remove(f"resources/temp/{filename}")
    
    @app_commands.command(description=clocal.get("party", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("party", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("party", {}).get("DESCRIBE", {}).get("password", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def party(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        user_data = endpoint.fetch_partyid_from_puuid(False)
        if user_data.get("CurrentPartyID")==None:
            raise ValorantBotError(response.get("FAILED"))
        party_details = endpoint.fetch_party_details(party_id = user_data.get("CurrentPartyID", ""))

        temp_embeds = GetEmbed.party(endpoint.player, endpoint.puuid, party_details, endpoint, response)
        main_embed, embeds = temp_embeds[0], temp_embeds[1]
        
        if len(embeds)>6:
            for i in range(math.ceil(len(embeds) / 5)):
                e = embeds[0+(i*5):5+(i*5)]
                if i==0:
                    e.insert(0, main_embed)
                await interaction.followup.send(embeds=e, view=View.share_button(interaction, e) if is_private_message else MISSING)
        else:
            embeds.insert(0, main_embed)
            await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("custom", {}).get("DESCRIPTION", ""))
    @app_commands.describe(username=clocal.get("custom", {}).get("DESCRIBE", {}).get("username", ""), password=clocal.get("custom", {}).get("DESCRIBE", {}).get("password", ""), random=clocal.get("custom", {}).get("DESCRIBE", {}).get("random", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def custom(self, interaction: Interaction, random: bool = False, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        response["RESULT"] = {
            "WIN": "VICTORY",
            "LOSE": "DEFEAT",
            "DRAW": "DRAW"
        }
        response["QUEUE"] = {
            "unknown": "Unknown",
            "unrated": "Unrated",
            "competitive": "Competitive",
            "deathmatch": "Deathmatch",
            "ggteam": "Escalation",
            "onefa": "Replication",
            "custom": "Custom",
            "newmap": "New Map",
            "snowball": "Snowball Fight",
            "spikerush": "Spike Rush"
        }
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        user_data = endpoint.fetch_partyid_from_puuid(False)
        if user_data.get("CurrentPartyID")==None:
            raise ValorantBotError(response.get("FAILED"))
        party_details = endpoint.fetch_party_details(party_id = user_data.get("CurrentPartyID", ""))
        
        # Embeds
        embeds = GetEmbed.custom(endpoint.puuid, party_details, endpoint, response)
        
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        await self.check_update(interaction)
    
    @app_commands.command(description=clocal.get("article", {}).get("DESCRIPTION", ""))
    @app_commands.describe(category=clocal.get("article", {}).get("DESCRIBE", {}).get("category", ""), article=clocal.get("article", {}).get("DESCRIBE", {}).get("article", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def article(self, interaction: Interaction, category: Literal["Game Updates", "Development", "Esports", "Announcments"]=None, article: int=1) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)

        # endpoint
        endpoint = API_ENDPOINT()

        languages_list = ["en-us", "en-gb", "de-de", "es-es", "es-mx", "fr-fr", "it-it", "ja-jp", "ko-kr", "pt-br", "ru-ru", "tr-tr", "vi-vn"]
        locale = str(VLR_locale).lower() if str(VLR_locale).lower() in languages_list else "en-us"
        data = endpoint.fetch_article(locale)

        if data==None:
            raise ValorantBotError(response.get("NOT_FOUND"))

        # articles
        if article <= 1: article = 1
        elif article >= 10: article = 10

        category_list = {
            "Game Updates": "game_updates",
            "Development": "dev",
            "Esports": "esports",
            "Announcments": "announcments"
        }

        article_data = []
        if category==None:
            if len(data)<article:
                article = len(data)
            article_data = data[:article]
        else:
            category = category_list[category]

            i = 0
            while len(article_data)<article:
                if len(data)==i:
                    break

                if data[i].get("category")==category:
                    article_data.append(data[i])
                i += 1

        if len(article_data) > 0:
            embeds = []
            for d in article_data:
                embeds.append(GetEmbed.article_embed(d, response))
            await interaction.followup.send(embeds=embeds)
            await self.check_update(interaction)
        else:
            raise ValorantBotError(response.get("NOT_FOUND"))
        

    @app_commands.command(description=clocal.get("debug", {}).get("DESCRIPTION", ""))
    @app_commands.describe(action=clocal.get("debug", {}).get("DESCRIBE", {}).get("action", ""))
    @app_commands.guild_only()
    @owner_only()
    async def debug(self, interaction: Interaction, action: Literal['Reload Skin Price', 'Reload Emoji', 'Reload Cache', 'Reset Emoji', 'Reset Cache']) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer(ephemeral=True)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        if action == 'Reload Skin Price':
            # endpoint
            endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)
            
            # fetch skin price
            skin_price = endpoint.store_fetch_offers()
            self.db.insert_skin_price(skin_price, force=True)

            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(action=action)))
        
        elif action == 'Reload Emoji':
            ret = await setup_emoji(self.bot, interaction.guild, interaction.locale, force=True)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(action=action) + "\n\n" + ret))
        
        elif action == 'Reload Cache':
            self.funtion_reload_cache(force=True)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(action=action)))
        
        elif action == 'Reset Emoji':
            ret = await setup_emoji(self.bot, interaction.guild, interaction.locale, force=True, reset=True)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(action=action) + "\n\n" + ret))
        
        elif action == 'Reset Cache':
            from utils.valorant.cache import get_cache
            get_cache(self.bot.bot_version)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(action=action)))
        
        

async def setup(bot: ValorantBot) -> None:
    await bot.add_cog(ValorantCog(bot))
