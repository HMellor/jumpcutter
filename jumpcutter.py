import os
import re
import math
import argparse
import subprocess
import numpy as np
from pytube import YouTube
from scipy.io import wavfile
from audiotsm import phasevocoder
from shutil import copyfile, rmtree
from audiotsm.io.wav import WavReader, WavWriter


def downloadFile(save_dir, url):
    correct_filename = False
    while not correct_filename:
        video_stream = YouTube(url).streams.get_highest_resolution()
        file_name = video_stream.default_filename
        if file_name != 'YouTube.mp4':
            correct_filename = True
    output_path = os.path.join(save_dir, file_name)
    output_path = output_path.replace(' ', '_')
    if os.path.isfile(output_path):
        print('Already downloaded: {}'.format(video_stream.title))
        newname = output_path
    else:
        print('Downloading: {}'.format(video_stream.title))
        name = video_stream.download(output_path=os.path.dirname(output_path))
        newname = name.replace(' ', '_')
        os.rename(name, newname)
    return newname


def getMaxVolume(s):
    maxv = float(np.max(s))
    minv = float(np.min(s))
    return max(maxv, -minv)


def copyFrame(inputFrame, outputFrame):
    src = "{}/frame{:06d}.jpg".format(temp_dir, inputFrame + 1)
    dst = "{}/newFrame{:06d}.jpg".format(temp_dir, outputFrame + 1)
    if not os.path.isfile(src):
        return False
    copyfile(src, dst)
    if outputFrame % 20 == 19:
        print('\r' + str(outputFrame + 1) + " time-altered frames saved", end = '')
    return True


def reset_dir(s):
    try:
        deletePath(s)
        os.mkdir(s)
        print('Directory {} reset'.format(s))
    except OSError as e:
        print("Error: {} \nCreation of the directory {} failed. (The TEMP folder may already exist. Delete or rename it, and try again.)".format(e.strerror, s))


def deletePath(s):  # Dangerous! Watch out!
    if os.path.isdir(s):
        try:
            rmtree(s, ignore_errors=False)
            print('Directory {} deleted'.format(s))
        except OSError as e:
            print('Deletion of the directory {} failed'.format(s))
            print(e.strerror)
    else:
        print('Directory does not exist, skippig deletion of {}'.format(s))


parser = argparse.ArgumentParser(description='Modifies a video file to play at different speeds when there is sound vs. silence.')
parser.add_argument('--input_path', type=str,  help='the video file you want modified')
parser.add_argument('--url', type=str, help='A youtube url to download and process')
parser.add_argument('--output_dir', type=str, default="./", help="the output directory. (optional. if not included, it'll just modify the input file name)")
parser.add_argument('--silent_threshold', type=float, default=0.03, help="the volume amount that frames' audio needs to surpass to be consider \"sounded\". It ranges from 0 (silence) to 1 (max volume)")
parser.add_argument('--sounded_speed', type=float, default=1.00, help="the speed that sounded (spoken) frames should be played at. Typically 1.")
parser.add_argument('--silent_speed', type=float, default=5.00, help="the speed that silent frames should be played at. 999999 for jumpcutting.")
parser.add_argument('--frame_margin', type=float, default=1, help="some silent frames adjacent to sounded frames are included to provide context. How many frames on either the side of speech should be included? That's this variable.")
parser.add_argument('--sample_rate', type=float, default=44100, help="sample rate of the input and output videos")
parser.add_argument('--frame_rate', type=float, default=30, help="frame rate of the input and output videos. optional... I try to find it out myself, but it doesn't always work.")
parser.add_argument('--frame_quality', type=int, default=3, help="quality of frames to be extracted from input video. 1 is highest, 31 is lowest, 3 is the default.")

args = parser.parse_args()

try:
    frameRate = args.frame_rate
    sample_rate = args.sample_rate
    silent_threshold = args.silent_threshold
    frame_spreadage = args.frame_margin
    new_speed = [args.silent_speed, args.sounded_speed]
    # define directories to use in batch processing
    root = 'C:/users/hejme/Desktop/speedy_lectures'
    working_dir = os.path.join(root, 'temp')
    download_dir = os.path.join(root, 'input')
    output_dir = os.path.join(root, 'output')
    if not os.path.exists(working_dir):
        os.mkdir(working_dir)
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    # get input path from args.url or args.input_path
    if args.url is not None:
        input_path = downloadFile(download_dir, args.url)
    else:
        input_path = args.input_path
    url = args.url
    frame_quality = args.frame_quality

    assert input_path is not None, "why u put no input file, that dum"

    if len(args.output_dir) >= 1:
        output_dir = args.output_dir

    output_path = os.path.join(output_dir, os.path.basename(input_path))

    input_name = os.path.basename(input_path)[:-4]
    temp_dir = os.path.join(working_dir, input_name)
    AUDIO_FADE_ENVELOPE_SIZE = 400  # smooth out transitiion's audio by quickly fading in/out (arbitrary magic number whatever)

    reset_dir(temp_dir)

    command = "ffmpeg -i {} -qscale:v {} {}/frame%06d.jpg -hide_banner" .format(input_path, str(frame_quality), temp_dir)
    subprocess.call(command, shell=True)

    command = "ffmpeg -i {} -ab 160k -ac 2 -ar {} -vn {}/audio.wav" .format(input_path, str(sample_rate), temp_dir)

    subprocess.call(command, shell=True)

    command = "ffmpeg -i " + temp_dir + "/input.mp4 2>&1"
    f = open(temp_dir + "/params.txt", "w")
    subprocess.call(command, shell=True, stdout=f)


    sampleRate, audioData = wavfile.read(temp_dir + "/audio.wav")
    audioSampleCount = audioData.shape[0]
    maxAudioVolume = getMaxVolume(audioData)

    f = open(temp_dir + "/params.txt", 'r+')
    pre_params = f.read()
    f.close()
    params = pre_params.split('\n')
    for line in params:
        m = re.search('Stream #.*Video.* ([0-9]*) fps', line)
        if m is not None:
            frameRate = float(m.group(1))

    samplesPerFrame = sampleRate / frameRate

    audioFrameCount = int(math.ceil(audioSampleCount / samplesPerFrame))

    hasLoudAudio = np.zeros((audioFrameCount))


    for i in range(audioFrameCount):
        start = int(i * samplesPerFrame)
        end = min(int((i + 1) * samplesPerFrame), audioSampleCount)
        audiochunks = audioData[start:end]
        maxchunksVolume = float(getMaxVolume(audiochunks)) / maxAudioVolume
        if maxchunksVolume >= silent_threshold:
            hasLoudAudio[i] = 1

    chunks = [[0, 0, 0]]
    shouldIncludeFrame = np.zeros((audioFrameCount))
    for i in range(audioFrameCount):
        start = int(max(0, i - frame_spreadage))
        end = int(min(audioFrameCount, i + 1 + frame_spreadage))
        shouldIncludeFrame[i] = np.max(hasLoudAudio[start:end])
        if (i >= 1 and shouldIncludeFrame[i] != shouldIncludeFrame[i - 1]):  # Did we flip?
            chunks.append([chunks[-1][1], i, shouldIncludeFrame[i - 1]])

    chunks.append([chunks[-1][1], audioFrameCount, shouldIncludeFrame[i - 1]])
    chunks = chunks[1:]

    outputAudioData = np.zeros((0, audioData.shape[1]))
    outputPointer = 0

    lastExistingFrame = None
    for chunk in chunks:
        audioChunk = audioData[int(chunk[0] * samplesPerFrame):int(chunk[1] * samplesPerFrame)]

        sFile = temp_dir + "/tempStart.wav"
        eFile = temp_dir + "/tempEnd.wav"
        wavfile.write(sFile, sample_rate, audioChunk)
        with WavReader(sFile) as reader:
            with WavWriter(eFile, reader.channels, reader.samplerate) as writer:
                tsm = phasevocoder(reader.channels, speed=new_speed[int(chunk[2])])
                tsm.run(reader, writer)
        _, alteredAudioData = wavfile.read(eFile)
        leng = alteredAudioData.shape[0]
        endPointer = outputPointer + leng
        outputAudioData = np.concatenate((outputAudioData, alteredAudioData / maxAudioVolume))

        #outputAudioData[outputPointer:endPointer] = alteredAudioData/maxAudioVolume

        # smooth out transitiion's audio by quickly fading in/out

        if leng < AUDIO_FADE_ENVELOPE_SIZE:
            outputAudioData[outputPointer:endPointer] = 0  # audio is less than 0.01 sec, let's just remove it.
        else:
            premask = np.arange(AUDIO_FADE_ENVELOPE_SIZE) / AUDIO_FADE_ENVELOPE_SIZE
            mask = np.repeat(premask[:, np.newaxis], 2, axis=1)  # make the fade-envelope mask stereo
            outputAudioData[outputPointer:outputPointer + AUDIO_FADE_ENVELOPE_SIZE] *= mask
            outputAudioData[endPointer - AUDIO_FADE_ENVELOPE_SIZE:endPointer] *= 1 - mask

        startOutputFrame = int(math.ceil(outputPointer / samplesPerFrame))
        endOutputFrame = int(math.ceil(endPointer / samplesPerFrame))
        for outputFrame in range(startOutputFrame, endOutputFrame):
            inputFrame = int(chunk[0] + new_speed[int(chunk[2])] * (outputFrame - startOutputFrame))
            didItWork = copyFrame(inputFrame, outputFrame)
            if didItWork:
                lastExistingFrame = inputFrame
            else:
                copyFrame(lastExistingFrame, outputFrame)

        outputPointer = endPointer

    print('')
    wavfile.write(temp_dir + "/audioNew.wav", sample_rate, outputAudioData)

    '''
    outputFrame = math.ceil(outputPointer/samplesPerFrame)
    for endGap in range(outputFrame,audioFrameCount):
        copyFrame(int(audioSampleCount/samplesPerFrame)-1,endGap)
    '''

    command = "ffmpeg -y -c:v mjpeg_cuvid -framerate {} -i {}/newFrame%06d.jpg -i {}/audioNew.wav -strict -2 -c:v h264_nvenc {}".format(str(frameRate), temp_dir, temp_dir, output_path)
    subprocess.call(command, shell=True)
finally:
    deletePath(temp_dir)
