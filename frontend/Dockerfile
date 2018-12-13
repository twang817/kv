FROM node:latest

RUN npm install --global \
    @vue/cli

WORKDIR /src
COPY . /src

RUN npm install

CMD npm run serve
