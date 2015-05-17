# Install the base image
FROM heroku/cedar:14

# make sure apt is up to date
RUN apt-get update

# install nodejs and npm
RUN apt-get install -y nodejs npm

# Install less & bower
RUN npm install -g less
RUN npm install -g bower

# Symlink /usr/bin/nodejs to /usr/bin/node
RUN ln -s /usr/bin/nodejs /usr/bin/node

RUN useradd -d /app -m app
USER app
WORKDIR /app/src

ENV HOME /app
ENV PATH /app/.heroku/python/bin:/tmp/python-pack/bin:$PATH
ENV STACK cedar-14
ENV PYTHONHOME /app/.heroku/python
ENV PYTHONPATH /app/
ENV DOCKER_BUILD 1


RUN mkdir -p /app/.heroku
RUN mkdir -p /tmp/app
RUN mkdir -p /app/src
RUN mkdir -p /app/.profile.d
RUN mkdir -p /tmp/python-pack
RUN mkdir -p /tmp/cache
RUN mkdir -p /tmp/environment


WORKDIR /app/src
WORKDIR /tmp/python-buildpack/bin

WORKDIR /app/
ONBUILD COPY . /app/

ONBUILD RUN git clone https://github.com/heroku/heroku-buildpack-python.git /tmp/python-pack --depth 1
ONBUILD RUN bash -l /tmp/python-pack/bin/compile /app /tmp/cache /app/.env

ONBUILD USER root
ONBUILD RUN cd /app/ && bower install --allow-root