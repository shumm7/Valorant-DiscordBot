from __future__ import annotations

import traceback
from datetime import datetime, time, timedelta, timezone
import dateutil.parser
from difflib import get_close_matches
from typing import Literal, Tuple, Any, TYPE_CHECKING

# Standard
import discord
from discord import (app_commands, Forbidden, HTTPException, Interaction)
from discord.ext import commands, tasks

from utils.errors import (
    ValorantBotError,
    AuthenticationError
)
from utils.config import GetColor
from utils.locale_v2 import ValorantTranslator
from utils.valorant import view as View
from utils.valorant.cache import create_json
from utils.valorant.db import DATABASE
from utils.valorant.embed import Embed, GetEmbed
from utils.valorant.endpoint import API_ENDPOINT
from utils.valorant.local import ResponseLanguage, LocalErrorResponse
from utils.valorant.useful import (format_relative, GetEmoji, GetItems, JSON, load_file)

VLR_locale = ValorantTranslator()
clocal = ResponseLanguage("", JSON.read("config", dir="config").get("command-description-language", "en-US"))

if TYPE_CHECKING:
    from bot import ValorantBot


class Notify(commands.Cog):
    def __init__(self, bot: ValorantBot) -> None:
        self.bot: ValorantBot = bot
        self.endpoint: API_ENDPOINT = None
        self.db: DATABASE = None
        self.notifys.start()
    
    def cog_unload(self) -> None:
        self.notifys.cancel()
        self.reload_article.cancel()
        self.check_auth.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.db = DATABASE()
        self.endpoint = API_ENDPOINT()
        self.reload_article.start()
        self.check_auth.start()
    
    async def get_endpoint_and_data(self, user_id: int) -> Tuple[API_ENDPOINT, Any]:
        data = await self.db.is_data(user_id, 'en-US')
        endpoint = self.endpoint
        endpoint.activate(data)
        return endpoint, data
    
    async def send_notify(self) -> None:
        notify_users = self.db.get_user_is_notify()
        user_data = JSON.read('users')
        notify_data = JSON.read('notifys')
        
        for user_id in notify_users:
            try:
                
                # endpoint
                endpoint, data = await self.get_endpoint_and_data(int(user_id))
                
                # offer
                offer = endpoint.store_fetch_storefront()
                skin_offer_list = offer["SkinsPanelLayout"]["SingleItemOffers"]
                duration = offer["SkinsPanelLayout"]["SingleItemOffersRemainingDurationInSeconds"]
                
                # author
                author = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(int(user_id))
                channel_send = author if data['dm_message'] else self.bot.get_channel(int(data['notify_channel']))
                
                # get guild language
                default_language = JSON.read("config", dir="config").get("default-language", "en-US")
                guild_locale = user_data.get(user_id, {}).get("lang", default_language)
                #get_guild_locale = [guild.preferred_locale for guild in self.bot.guilds if channel_send in guild.channels]
                #if len(get_guild_locale) > 0:
                #    guild_locale = guild_locale[0]
                response = ResponseLanguage('notify_send', guild_locale)
                
                user_skin_list = [skin for skin in notify_data if skin['id'] == str(user_id)]
                user_skin_list_uuid = [skin['uuid'] for skin in notify_data if skin['id'] == str(user_id)]
                
                if data['notify_mode'] == 'Specified':
                    skin_notify_list = list(set(skin_offer_list).intersection(set(user_skin_list_uuid)))
                    for noti in user_skin_list:
                        if noti['uuid'] in skin_notify_list:
                            uuid = noti['uuid']
                            skin = GetItems.get_skin(uuid)
                            name = skin['names'][guild_locale]
                            icon = skin['icon']
                            emoji = GetEmoji.tier_by_bot(uuid, self.bot)
                            
                            notify_send: str = response.get('RESPONSE_SPECIFIED')
                            duration = format_relative(datetime.utcnow() + timedelta(seconds=duration))
                            
                            embed = Embed(notify_send.format(emoji=emoji, name=name, duration=duration))
                            embed.set_thumbnail(url=icon)
                            view = View.NotifyView(user_id, uuid, name, ResponseLanguage('notify_add', guild_locale))
                            view.message = await channel_send.send(content=f'||{author.mention}||', embed=embed, view=view)
                
                elif data['notify_mode'] == 'All':
                    embeds = GetEmbed.notify_all_send(endpoint.player, offer, response, guild_locale, self.bot)
                    await channel_send.send(content=f'||{author.mention}||', embeds=embeds)
            
            except (KeyError, FileNotFoundError):
                print(f'{user_id} is not in notify list')
            except Forbidden:
                print("Bot don't have perm send notification message.")
                continue
            except HTTPException:
                print("Bot Can't send notification message.")
                continue
            except Exception as e:
                print(e)
                traceback.print_exception(type(e), e, e.__traceback__)
                continue
    
    async def send_article(self, notify_list: list, language: str) -> None:
        user_data = JSON.read('users')
        cache = JSON.read("article")
        for user_id in notify_list:
            try:
                # language
                default_language = JSON.read("config", dir="config").get("default-language", "en-US")
                guild_locale = user_data[user_id].get("lang", default_language)
                response = ResponseLanguage('notify_article', guild_locale)

                # author
                author = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(int(user_id))
                channel_send = author if user_data[user_id]['DM_Message'] else self.bot.get_channel(int(user_data[user_id]['notify_channel']))

                # embed
                article = cache[language][0]
                embed = GetEmbed.article_embed(article, response)

                await channel_send.send(embed=embed, content=f'||{author.mention}||')

            except (KeyError, FileNotFoundError):
                print(f'{user_id} is not in notify list')
            except Forbidden:
                print("Bot don't have perm send notification message.")
                continue
            except HTTPException:
                print("Bot Can't send notification message.")
                continue
            except Exception as e:
                print(e)
                traceback.print_exception(type(e), e, e.__traceback__)
                continue


    @tasks.loop(time=time(hour=0, minute=0, second=10))  # utc 00:00:15
    async def notifys(self) -> None:
        __verify_time = datetime.utcnow()
        if __verify_time.hour == 0:
            await self.send_notify()
    
    @tasks.loop(minutes=20)
    async def reload_article(self) -> None:
        cache = JSON.read("article")
        languages_list = ["en-us", "en-gb", "de-de", "es-es", "es-mx", "fr-fr", "it-it", "ja-jp", "ko-kr", "pt-br", "ru-ru", "tr-tr", "vi-vn"]

        for article_lang in languages_list:
            data = API_ENDPOINT().fetch_article(country_code = article_lang)
            if data!=None and type(data[0])==type({}):
                if data[0].get("url") != cache.get(article_lang, [{}])[0].get("url"): # Is Update
                    cache[article_lang] = data
                    JSON.save("article", cache)
                    
                    userdata = JSON.read("users")
                    notify_list = []

                    for user_id,values in userdata.items():
                        if values.get("lang", "en-US").lower() == article_lang and values.get("article", False) and (not data[0].get("category") in values.get("ignore_article_category", [])):
                            notify_list.append(user_id)
                    
                    await self.send_article(notify_list, article_lang)
    
    @tasks.loop(minutes=20)
    async def check_auth(self) -> None:
        users = self.db.read_db()

        for user_id, user in users.items():
            if user.get("auth_notify", False):
                author = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(int(user_id))
                local = LocalErrorResponse("AUTH", user.get("lang", "en-US"))
                for uuid, account in user.get("auth", {}).items():
                    if not account.get("notified_expire", False):
                        cookie = account.get("cookie", {}).get("ssid")
                        try:
                            await self.db.auth.login_with_cookie(cookie)
                        except Exception as e:
                            users[str(user_id)]["auth"][str(uuid)]["notified_expire"] = True
                            self.db.insert_user(users)
                            await author.send(embed=Embed(description=local.get("AUTO_CHECK").format(name=account.get("username"))))
        
    @notifys.before_loop
    async def before_daily_send(self) -> None:
        await self.bot.wait_until_ready()
        print(f'[{datetime.now()}] Checking new store skins for notifys.')
    
    notify = app_commands.Group(name='notify', description='Notify commands')
    
    @notify.command(name='add', description=clocal.get("notify_add", {}).get("DESCRIPTION", ""))
    @app_commands.describe(skin=clocal.get("notify_add", {}).get("DESCRIBE", {}).get("skin", ""))
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def notify_add(self, interaction: Interaction, skin: str) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 
        
        await interaction.response.defer()
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        # language
        
        response = ResponseLanguage('notify_add', interaction.locale)
        
        # # setup emoji 
        # await setup_emoji(self.bot, interaction.guild, interaction.locale)
        
        # check file whether
        create_json('notifys', [])
        
        # get cache
        skin_data = self.db.read_cache()
        
        # find skin
        skin_list = [skin_data['skins'][x]['names'][str(VLR_locale)] for x in skin_data['skins']]  # get skin list
        skin_name = get_close_matches(skin, skin_list, 1)  # get skin close match
        
        if skin_name:
            notify_data = JSON.read('notifys')
            
            find_skin = [x for x in skin_data['skins'] if skin_data['skins'][x]['names'][str(VLR_locale)] == skin_name[0]]
            skin_uuid = find_skin[0]
            skin_source = skin_data['skins'][skin_uuid]
            
            name = skin_source['names'][str(VLR_locale)]
            icon = skin_source['icon']
            uuid = skin_source['uuid']
            
            emoji = GetEmoji.tier_by_bot(skin_uuid, self.bot)
            
            for skin in notify_data:
                if skin['id'] == str(interaction.user.id) and skin['uuid'] == skin_uuid:
                    skin_already = response.get('SKIN_ALREADY_IN_LIST')
                    raise ValorantBotError(skin_already.format(emoji=emoji, skin=name))
            
            payload = dict(id=str(interaction.user.id), uuid=skin_uuid)
            
            try:
                notify_data.append(payload)
                JSON.save('notifys', notify_data)
            except AttributeError:
                notify_data = [payload]
                JSON.save('notifys', notify_data)
            
            # check if user is notify is on
            userdata = JSON.read('users')
            notify_mode = userdata.get(str(interaction.user.id), {}).get('notify_mode', None)
            if notify_mode is None:
                userdata[str(interaction.user.id)]['notify_mode'] = 'Specified'
                userdata[str(interaction.user.id)]['DM_Message'] = True
                JSON.save('users', userdata)
            
            success = response.get('SUCCESS')
            embed = Embed(success.format(emoji=emoji, skin=name))
            embed.set_thumbnail(url=icon)
            
            view = View.NotifyView(interaction.user.id, uuid, name, response)
            await interaction.followup.send(embed=embed, view=view)
            return
        
        raise ValorantBotError(response.get('NOT_FOUND'))
    
    @notify.command(name='list', description=clocal.get("notify_list", {}).get("DESCRIPTION", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_list(self, interaction: Interaction) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 
        
        await interaction.response.defer(ephemeral=True)
        
        response = ResponseLanguage('notify_list', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        view = View.NotifyViewList(interaction, response)
        await view.start()
    
    @notify.command(name='mode', description=clocal.get("notify_mode", {}).get("DESCRIPTION", ""))
    @app_commands.describe(mode=clocal.get("notify_mode", {}).get("DESCRIBE", {}).get("mode", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_mode(self, interaction: Interaction, mode: Literal['Specified Skin', 'All Skin', 'Off']) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.")       


        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage('notify_mode', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        if mode == 'Specified Skin':  # Check notify list if use mode specified skin
            self.db.check_notify_list(interaction.user.id)  # check total notify list
        
        self.db.change_notify_mode(interaction.user.id, mode)  # change notify mode
        
        success = response.get("SUCCESS")
        turn_off = response.get("TURN_OFF")
        
        embed = Embed(success.format(mode=mode))
        file: discord.File = None
        if mode == 'Specified Skin':
            file = load_file("resources/notify_mode_specified.png", "notify_mode_specified.png")
            embed.set_image(url=f'attachment://notify_mode_specified.png')
        elif mode == 'All Skin':
            file = load_file("resources/notify_mode_allskin.png", "notify_mode_allskin.png")
            embed.set_image(url=f'attachment://notify_mode_allskin.png')
        elif mode == 'Off':
            embed.description = turn_off
        
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    
    @notify.command(name='channel', description=clocal.get("notify_channel", {}).get("DESCRIPTION", ""))
    @app_commands.describe(channel=clocal.get("notify_channel", {}).get("DESCRIBE", {}).get("channel", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_channel(self, interaction: Interaction, channel: Literal['DM Message', 'Channel']) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage('notify_channel', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        self.db.check_notify_list(interaction.user.id)  # check total notify list
        self.db.change_notify_channel(interaction.user.id, channel, interaction.channel_id)  # change notify channel
        
        channel = '**DM Message**' if channel == 'DM Message' else f'{interaction.channel.mention}'
        
        embed = discord.Embed(description=response.get('SUCCESS').format(channel=channel), color=GetColor("success"))
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @notify.command(name='test', description=clocal.get("notify_test", {}).get("DESCRIPTION", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_test(self, interaction: Interaction) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 
        
        await interaction.response.defer(ephemeral=True)
        
        # language
        response_test = ResponseLanguage('notify_test', interaction.locale)
        response_send = ResponseLanguage('notify_send', interaction.locale)
        response_add = ResponseLanguage('notify_add', interaction.locale)
        
        # notify list
        notify_data = JSON.read('notifys')
        
        # get user data and offer
        endpoint, data = await self.get_endpoint_and_data(int(interaction.user.id))
        offer = endpoint.store_fetch_storefront()
        
        # offer data
        duration = offer["SkinsPanelLayout"]["SingleItemOffersRemainingDurationInSeconds"]
        user_skin_list = [skin for skin in notify_data if skin['id'] == str(interaction.user.id)]
        
        if len(user_skin_list) == 0 and data['notify_mode'] == 'Specified':
            empty_list = response_test.get('EMPTY_LIST')
            raise ValorantBotError(empty_list)
        
        channel_send = interaction.user if data['dm_message'] else self.bot.get_channel(int(data['notify_channel']))
        
        try:
            if data['notify_mode'] == 'Specified':
                for notify in user_skin_list:
                    uuid = notify['uuid']
                    skin = GetItems.get_skin(uuid)
                    
                    name = skin['names'][str(VLR_locale)]
                    icon = skin['icon']
                    emoji = GetEmoji.tier_by_bot(uuid, self.bot)
                    
                    notify_send: str = response_send.get('RESPONSE_SPECIFIED')
                    duration = format_relative(datetime.utcnow() + timedelta(seconds=duration))
                    
                    embed = Embed(notify_send.format(emoji=emoji, name=name, duration=duration))
                    embed.set_thumbnail(url=icon)
                    view = View.NotifyView(interaction.user.id, uuid, name, response_add)
                    view.message = await channel_send.send(embed=embed, view=view)
                    break
            
            elif data['notify_mode'] == 'All':
                embeds = GetEmbed.notify_all_send(endpoint.player, offer, response_send, str(VLR_locale), self.bot)
                await channel_send.send(embeds=embeds)
            
            else:
                raise ValorantBotError(response_test.get('NOTIFY_TURN_OFF'))
        
        except Forbidden:
            if channel_send == interaction.user:
                raise ValorantBotError(response_test.get('PLEASE_ALLOW_DM_MESSAGE'))
            raise ValorantBotError(response_test.get('BOT_MISSING_PERM'))
        except HTTPException:
            raise ValorantBotError(response_test.get('FAILED_SEND_NOTIFY'))
        except Exception as e:
            print(e)
            raise ValorantBotError(f"{response_test.get('FAILED_SEND_NOTIFY')} - {e}")
        else:
            await interaction.followup.send(embed=Embed(response_test.get('NOTIFY_IS_WORKING'), color=GetColor("success")), ephemeral=True)

    @notify.command(name='article', description=clocal.get("notify_article", {}).get("DESCRIPTION", ""))
    @app_commands.describe(notify=clocal.get("notify_article", {}).get("DESCRIBE", {}).get("notify", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_article(self, interaction: Interaction, notify: bool) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage('notify_article', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        self.db.change_article_notify_mode(interaction.user.id, notify)  # change notify mode
        
        if notify:
            file = load_file("resources/notify_article.png", "notify_article.png")
            embed = discord.Embed(description=response.get('ENABLED'), color=GetColor("success")).set_image(url="attachment://notify_article.png")
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            embed = discord.Embed(description=response.get('DISABLED'), color=GetColor("success"))
            await interaction.followup.send(embed=embed, ephemeral=True)
        
    @notify.command(name='update', description=clocal.get("notify_update", {}).get("DESCRIPTION", ""))
    @app_commands.describe(notify=clocal.get("notify_update", {}).get("DESCRIBE", {}).get("notify", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_update(self, interaction: Interaction, notify: bool) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage('notify_update', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        self.db.change_update_notify_mode(interaction.user.id, notify)  # change notify mode
        
        if notify:
            embed = discord.Embed(description=response.get('ENABLED'), color=GetColor("success"))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(description=response.get('DISABLED'), color=GetColor("success"))
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @notify.command(name='category', description=clocal.get("notify_category", {}).get("DESCRIPTION", ""))
    @app_commands.describe(category=clocal.get("notify_category", {}).get("DESCRIBE", {}).get("category", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_category(self, interaction: Interaction, category: Literal["Game Updates", "Development", "Esports", "Announcments"]) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage('notify_category', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        category_list = {
            "Game Updates": "game_updates",
            "Development": "dev",
            "Esports": "esports",
            "Announcments": "announcments"
        }
        list = self.db.change_ignore_article_category(interaction.user.id, category_list[category])  # change notify mode
        
        category_text = ""
        for cat in list:
            if len(category_text)!=0:
                category_text += "｜"
            category_text += response.get("CATEGORY", {}).get(cat, "None")
        if len(list)==0:
            category_text = response.get("NO_CATEGORY")

        embed = discord.Embed(description=response.get('SUCCESS').format(category=category_text), color=GetColor("success"))
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    
    @notify.command(name='auth', description=clocal.get("notify_auth", {}).get("DESCRIPTION", ""))
    @app_commands.describe(notify=clocal.get("notify_auth", {}).get("DESCRIBE", {}).get("notify", ""))
    # @dynamic_cooldown(cooldown_5s)
    async def notify_auth(self, interaction: Interaction, notify: bool) -> None:
        print(f"[{datetime.now()}] {interaction.user.name} issued a command /notify {interaction.command.name}.") 

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage('notify_auth', interaction.locale)
        
        await self.db.is_data(interaction.user.id, interaction.locale)  # check if user is in db
        
        self.db.change_auth_notify_mode(interaction.user.id, notify)  # change notify mode
        
        if notify:
            file = load_file("resources/notify_auth.png", "notify_auth.png")
            embed = discord.Embed(description=response.get('ENABLED'), color=GetColor("success")).set_image(url="attachment://notify_auth.png")
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            embed = discord.Embed(description=response.get('DISABLED'), color=GetColor("success"))
            await interaction.followup.send(embed=embed, ephemeral=True)

    # @notify.command(name='manage', description='Manage notification list.')
    # @owner_only()
    # async def notify_manage(self, interaction: Interaction) -> None:
    #     ...


async def setup(bot: ValorantBot) -> None:
    await bot.add_cog(Notify(bot))
