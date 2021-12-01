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
BOT_TOKEN = os.environ['token']
NAME = os.environ['name']
MESSAGE_CHANNEL = int(os.environ['channel'])
MIN_PLAYER_AMOUNT = int(os.environ['minplayeramount'])
AMOUNT_OF_PREVIOUS_REQUESTS = int(os.environ['prevrequestcount'])
STARTED_AMOUNT = int(os.environ['startedamount'])

#config
# BOT_TOKEN = ""  # https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token
# NAME = '[BOB] GUNMASTER' # name of the server it needs to search for

# extra's:
# MESSAGE_CHANNEL = 0 # channel where it needs to post the message if almost empty etc.
# MIN_PLAYER_AMOUNT = 20 # amount of change needed to count
# AMOUNT_OF_PREVIOUS_REQUESTS = 5 # amount of request to use for the calculation if the difference is more thatn min_player_amount
# STARTED_AMOUNT = 50 # amount of players before it calls the server "started"
# GUILD = 0 # discord group id where is needs to post the message
# choose image from the sample files, they will auto-update in code.
AVATARIMAGE = "map_mode" #.png - image to show as avatar
MESSAGEIMAGE = "map_mode" #.png - image you want to show in message
SMALLFONT = "DejaVuSans.ttf" # fontfile used in the image
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
                    if newstatus['serverInfo'] != status:  # avoid spam to the discord API
                        await self.change_presence(activity=discord.Game(newstatus['serverInfo']))
                        status = newstatus['serverInfo']
                    # send messages
                    try:
                        if MESSAGE_CHANNEL != 0:
                            global sinceEmpty
                            global sincePlayerTrigger  # to not let it spam
                            test = False
                            for request in previousRequests:
                                if float(request)-float(newstatus["playerAmount"]) >= MIN_PLAYER_AMOUNT and sincePlayerTrigger > AMOUNT_OF_PREVIOUS_REQUESTS*2: # check last few requests for changes
                                    await createMessage(self, MESSAGEIMAGE, newstatus, f"I'm low on players! Join me now!", f"Perfect time to join without queue!\n{newstatus['serverInfo']}")
                                    sincePlayerTrigger = 0
                                    test = True
                                    break
                            if not test: # if none worked
                                sincePlayerTrigger += 1
    
                            if newstatus["playerAmount"] <= 5: # counter since empty
                                sinceEmpty = True
    
                            if sinceEmpty == True and newstatus["playerAmount"] >= STARTED_AMOUNT: # run if 1 hour after starting and playercount is good
                                await createMessage(self, MESSAGEIMAGE, newstatus, f"I'm up and running!", f"Feeling good :slight_smile:\n{newstatus['serverInfo']}")
                                sinceEmpty = False
    
                            if newstatus["playerAmount"] >= MIN_PLAYER_AMOUNT and len(previousRequests) >= AMOUNT_OF_PREVIOUS_REQUESTS: # if current is above or at 20 players and runs for at least a few mins
                                if all(MIN_PLAYER_AMOUNT>request for request in previousRequests): # if the past messages are below 20
                                    await createMessage(self, MESSAGEIMAGE, newstatus, f"Pre-round is over!", f"No more waiting. If you join now you can instantly play.\n{newstatus['serverInfo']}")
    
                            if len(previousRequests) >= AMOUNT_OF_PREVIOUS_REQUESTS: # if it has run more than 4 times
                                previousRequests.pop(0) # remove first item
                            previousRequests.append(newstatus["playerAmount"]) # add current in back
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        print(f"messageSend: {e} - line {exc_tb.tb_lineno} {fname}")
                    # change picture
                    if picture != newstatus["serverMap"]:
                        picture = newstatus["serverMap"]
                        with open(f'{AVATARIMAGE}.png', 'rb') as f: 
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
    embed.set_footer(text=f"player threshold set to {MIN_PLAYER_AMOUNT} players, checks difference of previous {(AMOUNT_OF_PREVIOUS_REQUESTS*2)} minutes and in-between")
    embed.set_thumbnail(url=f"attachment://{image_url}.png") # small image
    # embed.set_image(url=f"attachment://{image_url}.png") # bigger image
    await channel.send(embed=embed, file=file)

async def get_playercount(session):
    try:
        url = f"https://api.gametools.network/bf2042/servers/?name={urllib.parse.quote(NAME)}&limit=1"
        async with session.get(url=url) as r:
            response = await r.json()
    except Exception as e:
        print(f"Server not found or api.gametools.network unreachable - {e}")
        return
    
    try:
        players = response["servers"][0]['playerAmount']
        maxPlayers = response["servers"][0]['maxPlayers']
        inQue = response["servers"][0]['inQue']
        serverMap = response["servers"][0]['currentMap']
        if inQue == None:
            inQue = 0
            serverInfo = f"{players}/{maxPlayers} - {serverMap}"  # discord status message
        else:
            serverInfo = f"{players}/{maxPlayers} [{inQue}] - {serverMap}"  # discord status message

        # dont allow names longer than 30 characters
        prefix = response["servers"][0]['prefix'][0:30]

        # create image with only map
        url = response["servers"][0]['url']
        async with session.get(url=url) as r:
            image = await r.read()
        file = open("map_image.png", "wb")
        file.write(image)
        file.close()

        # create image with mapmode
        mode = response["servers"][0]['mode']
        smallmode = ""
        if mode == "Conquest":
            smallmode = "CQ"
        elif mode == "Conquest large":
            smallmode = "CL"
        elif mode == "Rush":
            smallmode = "RS"
        elif mode == "Custom":
            smallmode = "CM"

        #creating the images:
        img = Image.open("map_image.png")
        img = img.convert("RGBA")

        tint = Image.new("RGBA", (300, 146), (0, 0, 0, 80))
        img = Image.alpha_composite(img, tint)

        font = ImageFont.truetype(BIGFONT, size=75, index=0)

        # draw smallmode
        draw = ImageDraw.Draw(img)
        w, h = draw.textsize(smallmode, font=font)
        draw.text(((300 - w) / 2, (146 - h) / 3), smallmode, font=font)
        img.save('map_mode.png')

        return {"serverInfo": serverInfo, "serverName": prefix, "serverMap": serverMap, "playerAmount": inQue+players}

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
    LivePlayercountBot().run(BOT_TOKEN)
