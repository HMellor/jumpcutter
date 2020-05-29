import signal
import requests
import argparse
import subprocess
import multiprocessing
from bs4 import BeautifulSoup


def getPlaylistLinks(url):
    link_list = []
    correct_playlist = False
    while not correct_playlist:
        sourceCode = requests.get(url).text
        soup = BeautifulSoup(sourceCode, 'html.parser')
        domain = 'https://www.youtube.com'
        playlist_name = soup.find('title').text
        if playlist_name != 'YouTube':
            correct_playlist = True
    print('Getting links for: ' + playlist_name)
    while len(link_list) == 0:
        links = soup.find_all("a", {"dir": "ltr"})
        for link in links:
            href = link.get('href')
            if href.startswith('/watch?'):
                link_list.append(domain + href)
    print('{} links collected'.format(len(link_list)))
    return link_list


def cut_video(url):
    output_dir = 'C:/users/hejme/Desktop/speedy_lectures/output'
    command = 'python ./jumpcutter.py --output_dir "{}" --sounded_speed {} --silent_speed {} --url "{}"'.format(output_dir, 2., 8., url)
    subprocess.call(command, shell=True)


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def cut_all_videos(urls):
    # only use as many cores as necessary
    num_cpus = min(multiprocessing.cpu_count(), len(urls))
    print('Utilising {} cpu cores'.format(num_cpus))
    with multiprocessing.Pool(num_cpus, init_worker) as pool:
        try:
            pool.map(cut_video, urls)
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Takes a youtube playlist and and condenses each video using jumpcutter.')
    parser.add_argument('--playlist_url', '-p', type=str,  help='the url of the playlist to cut down')
    args = parser.parse_args()

    urls = getPlaylistLinks(args.playlist_url)
    cut_all_videos(urls)
