#!/bin/sh

bash build.sh
docker run --rm -ti --name vncmqtt-test --env-file test.env jamesandariese/vncmqtt:latest
