#!/bin/bash

pid=`pgrep ffmpeg`
kill "$pid"