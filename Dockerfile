#https://docs.docker.com/develop/develop-images/dockerfile_best-practices/

#https://docs.docker.com/engine/reference/builder/

FROM python:3

WORKDIR /usr/src/app

ENV token default_token_value
ENV name default_name_value
ENV channel default_channel_value
ENV minplayeramount '20'
ENV prevrequestcount '5'
ENV startedamount '50'
ENV guild default_guild_value
ENV lang 'en-us'
ENV guid 'false'

RUN pip install --no-cache-dir aiohttp discord urllib3 Pillow

COPY ./s1.py /usr/src/app
COPY ./DejaVuSans.ttf /usr/src/app

CMD [ "python", "./s1.py" ]
