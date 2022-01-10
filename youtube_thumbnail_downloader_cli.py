# -*- coding: utf-8 -*-
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.webdriver import WebDriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from time import sleep
import argparse
import requests
import os
import re

p_clip = re.compile(r"/watch\?[a-zA-Z0-9?&=_-]*?v=(?P<vid>[a-zA-Z0-9_-]+)&?")
p_playlist = re.compile(r"/(watch|playlist)\?[a-zA-Z0-9?&=_-]*?list=(?P<playlist>[a-zA-Z0-9_-]+)&?")
p_channel = re.compile(r"youtube\.com/(?P<channel>(c/|user/|channel/)?[\w%-]+)/?")
p_vid = re.compile(r"(/embed|youtu\.be)/(?P<vid>[a-zA-Z0-9_-]+)\??")

parser = argparse.ArgumentParser()
parser.add_argument('--url', type=str, default='', help="the url to extract thumbnails")
parser.add_argument('--save_dir', type=str, default='./thumbnails', help="the path to save thumbnails")
args = parser.parse_args()

def main():
    save_dir = args.save_dir
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
        except Exception:
            print('wrong path')
            exit(0)

    url = args.url
    s_clip = p_clip.search(url)
    s_playlist = p_playlist.search(url)
    s_channel = p_channel.search(url)
    s_vid = p_vid.search(url)

    if s_clip:
        vid = s_clip.group('vid')
        if s_playlist:
            answer = input('This video is a part of a playlist. Would you like to download whole playlist? (y/n) ').strip()
            if answer == 'y':
                playlist = s_playlist.group('playlist')
                playlist_url = f'https://youtube.com/playlist?list={playlist}'
                download_list(playlist_url)
            else:
                try:
                    video_url = f'https://www.youtube.com/watch?v={vid}'
                    download_clip(video_url)
                except KeyboardInterrupt:
                    print(f'Failure: default_{vid}.jpg')
        else:
            try:
                video_url = f'https://www.youtube.com/watch?v={vid}'
                download_clip(video_url)
            except KeyboardInterrupt:
                print(f'Failure: default_{vid}.jpg')
    elif s_playlist:
        playlist = s_playlist.group('playlist')
        playlist_url = f'https://youtube.com/playlist?list={playlist}'
        download_list(playlist_url)
    elif s_channel:
        channel = s_channel.group('channel')
        channel_url = f'https://youtube.com/{channel}/videos?sort=da'
        download_list(channel_url)
    elif s_vid:
        vid = s_vid.group('vid')
        try:
            video_url = f'https://www.youtube.com/watch?v={vid}'
            download_clip(video_url)
        except KeyboardInterrupt:
            print(f'Failure: default_{vid}.jpg')
    else:
        print('wrong url')
        exit(0)

def download_clip(url):
    thumbnails = ['maxresdefault', 'sddefault', 'hqdefault', 'mqdefault', 'default']
    vid = p_clip.search(url).group('vid')
    is_success = False
    for thumbnail in thumbnails:
        thumbnail_url = f'https://img.youtube.com/vi/{vid}/{thumbnail}.jpg'
        thumbnail_res = requests.get(thumbnail_url)
        if thumbnail_res.status_code == 200:
            file_name = f'{thumbnail}_{vid}.jpg'
            thumbnail_bin = thumbnail_res.content
            with open(os.path.join(args.save_dir, file_name), 'wb') as f:
                f.write(thumbnail_bin)
            is_success = True
            break
    if is_success:
        print(f'Download: {file_name}')
    else:
        print(f'Failure: default_{vid}.jpg')
    return is_success

def download_list(url):
    try:
        options = Options()
        options.add_argument('window-size=1280,720')
        options.add_argument('headless')
        options.add_argument('disable-gpu')
        service = Service(EdgeChromiumDriverManager().install())
        driver = WebDriver(service=service, options=options)
        driver.implicitly_wait(5)
    except (KeyboardInterrupt, Exception):
        print('Failed to load web driver')
        exit(0)

    try:
        driver.get(url)

        elements = driver.find_elements(By.XPATH, '//*[@id="video-title"]')
        last_num = len(elements)
        reload_count = 0

        while reload_count < 3:
            print(f'{last_num} Loaded')
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            sleep(1)

            elements = driver.find_elements(By.XPATH, '//*[@id="video-title"]')
            current_num = len(elements)
            if last_num != current_num:
                last_num = current_num
                reload_count = 0
            else:
                reload_count += 1

        success_count = 0
        for i, element in enumerate(elements):
            video_url = element.get_attribute('href')
            print(f'({i+1}/{last_num}) ', end='')
            try:
                is_success = download_clip(video_url)
            except KeyboardInterrupt:
                vid = p_clip.search(video_url).group('vid')
                print(f'Failure: default_{vid}.jpg')
                raise KeyboardInterrupt
            if is_success:
                success_count += 1
    except KeyboardInterrupt:
        if not 'success_count' in locals() or not 'last_num' in locals():
            success_count = 0
            last_num = 0
    finally:
        print(f'({success_count}/{last_num}) Success')
        driver.quit()

if __name__ == '__main__':
    main()
