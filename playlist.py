import signal
import requests
import argparse
import subprocess
import multiprocessing
from bs4 import BeautifulSoup


def getPlaylistLinks(url):
    videos = {}
    correct_playlist = False
    while not correct_playlist:
        sourceCode = requests.get(url).text
        soup = BeautifulSoup(sourceCode, 'html.parser')
        domain = 'https://www.youtube.com'
        playlist_name = soup.find('title').text
        if playlist_name != 'YouTube':
            correct_playlist = True
    print('Getting links for: ' + playlist_name)
    while len(videos.keys()) == 0:
        links = soup.find_all("a", {"dir": "ltr"})
        for link in links:
            href = link.get('href')
            if href.startswith('/watch?'):
                videos[link.string.strip()] = domain + href
    print('{} links collected'.format(len(videos)))
    return videos


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


def repl():
    print('Please chose to convert a playlist or a single video?: [p/v]')
    to_convert = input()
    valid_answers = {'p', 'v'}
    assert to_convert in valid_answers, 'Bad selection, please choose from: (p, v)'
    print('Please provide the URL to fetch the video{} from:'.format('s' if to_convert == 'p' else ''))
    url = input()
    if to_convert == 'p':
        videos = getPlaylistLinks(url)
        print('Would you like to download all of the videos? [y/n]')
        download_all = input()
        valid_answers = {'y', 'n'}
        assert download_all in valid_answers, 'Bad selection, please choose from: (y, n)'
        if download_all == 'y':
            cut_all_videos(videos.values())
        elif download_all == 'n':
            print('Which video would you like to download?')
            indices = {}
            for i, name in enumerate(videos.keys()):
                indices[i] = name
                print('[{}] - {}'.format(i, name))
            video_index = int(input())
            valid_answers = {i for i in range(len(videos.keys()))}
            assert video_index in valid_answers, 'Bad selection, please choose one of the numbers in square brackets'
            print('You chose "{}"'.format(indices[video_index]))
            print('Was this correct? [y/n]')
            confirm_answer = input()
            valid_answers = {'y', 'n'}
            assert confirm_answer in valid_answers, 'Bad selection, please choose from: (y, n)'
            if confirm_answer == 'y':
                cut_video(videos[indices[video_index]])
            elif confirm_answer == 'n':
                print('Ok, restarting the selection process')

    elif to_convert == 'v':
        cut_video(url)
    repl()

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description='Takes a youtube playlist and and condenses each video using jumpcutter.')
    # parser.add_argument('--playlist_url', '-p', type=str,  help='the url of the playlist to cut down')
    # args = parser.parse_args()
    #
    # urls = getPlaylistLinks(args.playlist_url)
    # cut_all_videos(urls)
    repl()
