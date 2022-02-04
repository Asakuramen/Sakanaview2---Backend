#!/bin/bash

httpDir=~/www/img/live
cd $httpDir

# 過去ファイルを削除
rm $httpDir/stream/stream_*.ts
rm $httpDir/playlist.m3u8

ffmpeg \
-f alsa -thread_queue_size 1024 -i plughw:CARD=Camera,DEV=0 \
-f v4l2 -thread_queue_size 1024 -s 640x360 -i /dev/video0 \
-filter_complex scale=640x360,fps=15 \
-c:v h264_omx -b:v 764k -g 24 \
-c:a aac -b:a 64k \
-flags +cgop+global_header \
-f hls \
-hls_time 2 -hls_list_size 3 -hls_allow_cache 0 \
-hls_segment_filename $httpDir/stream/stream_%d.ts \
-hls_base_url stream/ \
-hls_flags delete_segments \
$httpDir/playlist.m3u8


