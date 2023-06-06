#!/usr/bin/python
# -*- coding: utf-8 -*-

# web requests
import aiohttp
import discord
import urllib.parse

# default OS
import os
import asyncio
import sys

# image stuff
from PIL import Image, ImageFont, ImageDraw

# # to run as docker image:
# BOT_TOKEN = os.environ['token']
# NAME = os.environ['name']
# GUID = os.environ['guid']
# MESSAGE_CHANNEL = int(os.environ['channel'])
# MIN_PLAYER_AMOUNT = int(os.environ['minplayeramount'])
# AMOUNT_OF_PREVIOUS_REQUESTS = int(os.environ['prevrequestcount'])
# STARTED_AMOUNT = int(os.environ['startedamount'])
# GUILD = int(os.environ['guild'])
# LANG = os.environ['lang']

# config
BOT_TOKEN = ""  # https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token
NAME = ""  # name of the server it needs to search for

# extra's:
MESSAGE_CHANNEL = 0  # channel where it needs to post the message if almost empty etc.
MIN_PLAYER_AMOUNT = 20  # amount of change needed to count
AMOUNT_OF_PREVIOUS_REQUESTS = 5  # amount of request to use for the calculation if the difference is more thatn min_player_amount
STARTED_AMOUNT = 50  # amount of players before it calls the server "started"
GUILD = 0  # discord group id where is needs to post the message
LANG = "en-us"  # language for the mapname etc.
GAME = (
    "bf1"  # game to use for the bot: bf4/bf1 (bfv doesnt have favorites amount visable)
)
NO_BOTS = False
# choose image from the sample files, they will auto-update in code.
AVATARIMAGE = "avatar_image"  # .png - image to show as avatar
MESSAGEIMAGE = "info_image"  # .png - image you want to show in message
SMALLFONT = "DejaVuSans.ttf"  # fontfile used in the image
BIGFONT = "Catamaran-SemiBold.ttf"

"""BF1 version"""
# dont change
sinceEmpty = False
previousRequests = []
sincePlayerTrigger = AMOUNT_OF_PREVIOUS_REQUESTS


class LivePlayercountBot(discord.Client):
    """Discord bot to display the Battlefield tracker's true playercount in the bot status"""

    async def on_ready(self):
        print(f"Logged on as {self.user}\n" f"Started monitoring server {NAME}")
        status = ""
        picture = ""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # change status
                    newstatus = await get_playercount(session)
                    if (
                        newstatus["serverInfo"] != status
                    ):  # avoid spam to the discord API
                        await self.change_presence(
                            activity=discord.Game(newstatus["serverInfo"])
                        )
                        status = newstatus["serverInfo"]
                    # send messages
                    try:
                        if MESSAGE_CHANNEL != 0:
                            global sinceEmpty
                            global sincePlayerTrigger  # to not let it spam
                            test = False
                            for request in previousRequests:
                                if (
                                    float(request) - float(newstatus["playerAmount"])
                                    >= MIN_PLAYER_AMOUNT
                                    and sincePlayerTrigger
                                    > AMOUNT_OF_PREVIOUS_REQUESTS * 2
                                ):  # check last few requests for changes
                                    await createMessage(
                                        self,
                                        MESSAGEIMAGE,
                                        newstatus,
                                        f"I'm low on players! Join me now!",
                                        f"Perfect time to join without queue!\n{newstatus['serverInfo']}",
                                    )
                                    sincePlayerTrigger = 0
                                    test = True
                                    break
                            if not test:  # if none worked
                                sincePlayerTrigger += 1

                            if newstatus["playerAmount"] <= 5:  # counter since empty
                                sinceEmpty = True

                            if (
                                sinceEmpty == True
                                and newstatus["playerAmount"] >= STARTED_AMOUNT
                            ):  # run if 1 hour after starting and playercount is good
                                await createMessage(
                                    self,
                                    MESSAGEIMAGE,
                                    newstatus,
                                    f"I'm up and running!",
                                    f"Feeling good :slight_smile:\n{newstatus['serverInfo']}",
                                )
                                sinceEmpty = False

                            if (
                                newstatus["playerAmount"] >= MIN_PLAYER_AMOUNT
                                and len(previousRequests) >= AMOUNT_OF_PREVIOUS_REQUESTS
                            ):  # if current is above or at 20 players and runs for at least a few mins
                                if all(
                                    MIN_PLAYER_AMOUNT > request
                                    for request in previousRequests
                                ):  # if the past messages are below 20
                                    await createMessage(
                                        self,
                                        MESSAGEIMAGE,
                                        newstatus,
                                        f"Pre-round is over!",
                                        f"No more waiting. If you join now you can instantly play.\n{newstatus['serverInfo']}",
                                    )

                            if (
                                len(previousRequests) >= AMOUNT_OF_PREVIOUS_REQUESTS
                            ):  # if it has run more than 4 times
                                previousRequests.pop(0)  # remove first item
                            previousRequests.append(
                                newstatus["playerAmount"]
                            )  # add current in back
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        print(f"messageSend: {e} - line {exc_tb.tb_lineno} {fname}")
                    # change picture
                    if picture != newstatus["serverMap"]:
                        picture = newstatus["serverMap"]
                        with open(f"{AVATARIMAGE}.png", "rb") as f:
                            await self.user.edit(avatar=f.read())
                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print(f"updateStatus: {e} - line {exc_tb.tb_lineno} {fname}")
                await asyncio.sleep(120)


async def createMessage(self, image_url, newstatus, title, description):
    file = discord.File(f"{image_url}.png", filename=f"{image_url}.png")
    channel = self.get_channel(MESSAGE_CHANNEL)
    embed = discord.Embed(color=0xFFA500, title=title, description=description)
    embed.set_footer(
        text=f"player threshold set to {MIN_PLAYER_AMOUNT} players, checks difference of previous {(AMOUNT_OF_PREVIOUS_REQUESTS*2)} minutes and in-between"
    )
    embed.set_thumbnail(url=f"attachment://{image_url}.png")  # small image
    # embed.set_image(url=f"attachment://{image_url}.png") # bigger image
    await channel.send(embed=embed, file=file)


async def get_playercount(session):
    if GAME in ["bf2042", "bfv", "bf1", "bf4", "bf3", "bfh"]:
        try:
            url = f"https://api.gametools.network/{GAME}/detailedserver?name={urllib.parse.quote(NAME)}&lang={LANG}"
            async with session.get(url=url) as r:
                response = await r.json()
                # results
                players = (
                    response.get("noBotsPlayerAmount", 0)
                    if NO_BOTS and GAME == "bf4"
                    else response.get("playerAmount", 0)
                )
                maxPlayers = response.get("maxPlayerAmount", 0)
                inQue = response.get("inQueue", 0)
                serverMap = response.get("currentMap", "")
                prefix = response.get("prefix", "")[0:30]
                url = response.get("currentMapImage", "")
                mode = response.get("mode", "")
        except Exception as e:
            print(f"Server not found or api.gametools.network unreachable - {e}")
            return
    else:
        try:
            url = f"https://api.gametools.network/{GAME}/servers?name={urllib.parse.quote(NAME)}&lang={LANG}"
            async with session.get(url=url) as r:
                response = await r.json()
                first_result = response.get("servers", [])[0]
                players = first_result.get("playerAmount", 0)
                maxPlayers = first_result.get("maxPlayers", 0)
                inQue = first_result.get("inQueue", 0)
                serverMap = first_result.get("map", "")
                prefix = first_result.get("prefix", "")[0:30]
                url = first_result.get("mapImage", "")
                mode = first_result.get("mode", "")

        except Exception as e:
            print(f"Server not found or api.gametools.network unreachable - {e}")
            return

    try:
        # dont allow names longer than 30 characters
        serverInfo = (
            f"{players}/{maxPlayers} [{inQue}] - {serverMap}"  # discord status message
        )

        # create image with only map
        async with session.get(url=url) as r:
            image = await r.read()
        file = open("map_image.png", "wb")
        file.write(image)
        file.close()

        # create image with mapmode
        smallmode = ""
        if mode == "Conquest":
            smallmode = "CQ"
        elif mode == "Domination":
            smallmode = "DM"
        elif mode == "TugOfWar":
            smallmode = "FL"
        elif mode == "Rush":
            smallmode = "RS"
        elif mode == "BreakthroughLarge":
            smallmode = "OP"
        elif mode == "Breakthrough":
            smallmode = "SO"
        elif mode == "Possession":
            smallmode = "WP"
        elif mode == "TeamDeathMatch":
            smallmode = "TM"

        # creating the images:
        img = Image.open("map_image.png")
        img = img.convert("RGBA")

        tint = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 80))
        img = Image.alpha_composite(img, tint)

        font = ImageFont.truetype(BIGFONT, size=130, index=0)
        smallFont = ImageFont.truetype(SMALLFONT, size=35, index=0)
        favoritesFont = ImageFont.truetype(SMALLFONT, size=60, index=0)

        # draw smallmode
        draw = ImageDraw.Draw(img)
        _, _, w, h = draw.textbbox((0, 0), smallmode, font=font)
        draw.text(
            ((img.width - w) / 2, (img.height - h - 50) / 2), smallmode, font=font
        )
        img.save("map_mode.png")

        # get favorites
        if GAME in ["bf2042", "bf1", "bf4", "bf3", "bfh"]:
            serverBookmarkCount = response.get("favorites", 0)

            # draw bookmark
            img = Image.open("map_mode.png")
            draw = ImageDraw.Draw(img)
            serverCountMessage = "\u2605" + serverBookmarkCount
            _, _, w, h = draw.textbbox((0, 0), serverCountMessage, font=smallFont)
            draw.text(
                ((img.width - w) / 2 - 40, (img.height - h + 160) / 2),
                serverCountMessage,
                font=smallFont,
            )
        img.save("avatar_image.png")

        # draw infoImage
        img = Image.open("map_mode.png")
        draw = ImageDraw.Draw(img)
        if GAME in ["bf2042", "bf1", "bf4", "bf3", "bfh"]:
            serverCountMessage = "\u2605" + serverBookmarkCount
            _, _, w, h = draw.textbbox((0, 0), serverCountMessage, font=smallFont)
            draw.text(
                ((img.width - w) / 2, (img.height - h + 160) / 2),
                serverCountMessage,
                font=smallFont,
            )
        img.save("info_image.png")

        # draw bookmark
        img = Image.open("map_image.png")
        img = img.convert("RGBA")

        tint = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 80))
        img = Image.alpha_composite(img, tint)
        draw = ImageDraw.Draw(img)
        if GAME in ["bf2042", "bf1", "bf4", "bf3", "bfh"]:
            serverCountMessage = "\u2605" + serverBookmarkCount
            _, _, w, h = draw.textbbox((0, 0), serverCountMessage, font=favoritesFont)
            draw.text(
                ((img.width - w) / 2, (img.height - h) / 2),
                serverCountMessage,
                font=favoritesFont,
            )
        img.save("only_favorites_image.png")

        return {
            "serverInfo": serverInfo,
            "serverName": prefix,
            "serverMap": serverMap,
            "playerAmount": inQue + players,
        }

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f"playerList: {e} - line {exc_tb.tb_lineno} {fname}")


if __name__ == "__main__":
    assert sys.version_info >= (3, 6), "Script requires Python 3.6+"
    assert BOT_TOKEN and NAME, "Config is empty, pls fix"
    assert os.path.exists(BIGFONT), "fontfile not found"
    assert os.path.exists(SMALLFONT), "fontfile not found"
    print("Initiating bot")
    intents = discord.Intents.default()
    LivePlayercountBot(intents=intents).run(BOT_TOKEN)
