#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

import argparse
import copy
import os
import subprocess
from urllib.parse import parse_qs, urlparse
from collections import namedtuple
from queue import Queue
from threading import Thread
from xml.etree import ElementTree

import requests

namespaces = {"svg": "http://www.w3.org/2000/svg",
              "xlink": "http://www.w3.org/1999/xlink"}

Image = namedtuple("Image", ["id", "fname", "ts_in", "ts_out"])
Frame = namedtuple("Frame", ["fname", "ts_in", "ts_out"])


class Scrape:
    def __init__(self, host, id):
        self.host = host
        self.baseurl = "https://{}/presentation/{}".format(host, id)
        self.id = id

    def create_output_dir(self):
        self.out = "bbb-scrape-{}".format(self.id)
        try:
            os.mkdir(self.out)
        except FileExistsError:
            pass

    def fetch_shapes(self, force=False):
        file = os.path.join(self.out, "shapes.svg")
        if not os.path.exists(file) or force:
            url = "{}/shapes.svg".format(self.baseurl)
            shapes = requests.get(url)
            self.shapes = ElementTree.fromstring(shapes.content)
            open(file, "wb").write(shapes.content)
        else:
            self.shapes = ElementTree.fromstring(open(file, "r").read())

    def fetch_deskshare(self, force=False):
        fname = os.path.join(self.out, "deskshare.mp4")
        fname2 = os.path.join(self.out, "deskshare.xml")
        fname3 = os.path.join(self.out, "deskshare.webm")
        if not os.path.exists(fname) or force:
            url = "{}/deskshare/deskshare.mp4".format(self.baseurl)
            req = requests.get(url)
            if req.status_code == 200:
                print("reading ", url)
                open(fname, "wb").write(req.content)
            else:
                url = "{}/deskshare/deskshare.webm".format(self.baseurl)
                req = requests.get(url)
                if req.status_code == 200:
                    print("reading ", url)
                    open(fname3, "wb").write(req.content)
                else:
                    print("could not read deskshare video")
            url = "{}/deskshare.xml".format(self.baseurl)
            req = requests.get(url)
            print("deskshare.xml URL", url)
            if req.status_code == 200:
                open(fname2, "wb").write(req.content)
                return True
        fname = os.path.join(self.out, "deskshare.webm")
        if not os.path.exists(fname) or force:
            url = "{}/deskshare/deskshare.webm".format(self.baseurl)
            req = requests.get(url)
            if req.status_code == 200:
                open(fname, "wb").write(req.content)
                return True
        return False

    def url_file_exists(self, fname):
        url = "{}/video/{}".format(self.baseurl, fname)
        req = requests.get(url)
        if req.status_code == 200:
            return True
        else:
            return False

    def has_webcam_video(self):
        return self.url_file_exists("webcams.mp4")

    def has_webcam_audio_only(self):
        return self.url_file_exists("webcams.webm")

    def fetch_webcams(self, force=False):
        if self.has_webcam_video():
            url_fname = "webcams.mp4"
            fname = os.path.join(self.out, url_fname)
            print("fetching webcam video stream")
        else:
            url_fname = "webcams.webm"
            fname = os.path.join(self.out, url_fname)
            print("fetching webcam audio stream")
            if not self.has_webcam_audio_only():
                print("ERROR!!!")
        if not os.path.exists(fname) or force:
            url = "{}/video/{}".format(self.baseurl, url_fname)
            print("URL", url)
            req = requests.get(url)
            if req.status_code == 200:
                open(fname, "wb").write(req.content)
                return True
        fname = os.path.join(self.out, "webcams.webm")
        if not os.path.exists(fname) or force:
            url = "{}/video/webcams.webm".format(self.baseurl)
            req = requests.get(url)
            if req.status_code == 200:
                open(fname, "wb").write(req.content)
                return True
        return False

    def fetch_image(self, force=False):
        while self.workq.qsize() > 0:
            e = self.workq.get()
            href = e.attrib["{http://www.w3.org/1999/xlink}href"]
            try:
                uuid = os.path.dirname(href).split("/")[1]
                fname = "{}-{}".format(uuid, os.path.basename(href))
            except IndexError:
                fname = os.path.basename(href)
            file = os.path.join(self.out, fname)
            if not os.path.exists(file) or force:
                url = "{}/{}".format(self.baseurl, href)
                image = requests.get(url)
                open(file, "wb").write(image.content)
            e.attrib["{http://www.w3.org/1999/xlink}href"] = fname
            if "id" in e.attrib:
                self.images.append(Image(id=e.attrib["id"],
                                         fname=fname,
                                         ts_in=float(e.attrib["in"]),
                                         ts_out=float(e.attrib["out"])))
            self.workq.task_done()

    def fetch_images(self, tree=None, force=False):
        if tree is None:
            self.images = []
            self.workq = Queue()
            self.fetch_images(self.shapes, force)
            fname = os.path.join(self.out, "shapes.svg")
            open(fname, "wb").write(ElementTree.tostring(self.shapes))
            return

        for e in tree.findall("svg:image", namespaces):
            self.workq.put(e)
        for e in tree:
            self.fetch_images(e)

    def read_timestamps(self, tree=None):
        if tree is None:
            self.timestamps = []
            self.read_timestamps(self.shapes)
            self.timestamps = list(dict.fromkeys(self.timestamps))
            self.timestamps.sort()
            return

        for e in tree:
            if "in" in e.attrib:
                self.timestamps.append(float(e.attrib["in"]))
            if "out" in e.attrib:
                self.timestamps.append(float(e.attrib["out"]))
            if "timestamp" in e.attrib:
                self.timestamps.append(float(e.attrib["timestamp"]))
            self.read_timestamps(e)

    def generate_frames(self, force=False):
        try:
            os.mkdir(os.path.join(self.out, "frames"))
        except FileExistsError:
            pass
        self.frames = {}

        self.workq = Queue()

        t = 0.0
        for ts in self.timestamps[1:]:
            self.workq.put((t, ts))
            t = ts

        self.generate_frame(force)

    def generate_frame(self, force=False):
        while self.workq.qsize() > 0:
            (timestamp, ts_out) = self.workq.get()
            fname = os.path.join("frames", "shapes{}.png".format(timestamp))
            fnamesvg = os.path.join("frames", "shapes{}.svg".format(timestamp))
            if not os.path.exists(os.path.join(self.out, fnamesvg)) or force:
                shapes = copy.deepcopy(self.shapes)
                image = None
                for i in self.images:
                    if timestamp >= i.ts_in and timestamp < i.ts_out:
                        image = i.id
                for e in shapes.findall("svg:image", namespaces):
                    if e.attrib["id"] == image:
                        e.attrib["style"] = ""
                    else:
                        shapes.remove(e)
                for e in shapes.findall("svg:g", namespaces):
                    assert(e.attrib["class"] == "canvas")
                    if e.attrib["image"] == image:
                        e.attrib["display"] = "inherit"
                        self.make_visible(e, timestamp)
                    else:
                        shapes.remove(e)
                shapestr = ElementTree.tostring(shapes)
                open(os.path.join(self.out, fnamesvg), "wb").write(shapestr)

            if not os.path.exists(os.path.join(self.out, fname)) or force:
                result = subprocess.run(["inkscape", "--export-png={}".format(fname),
                                         "--export-area-drawing", fnamesvg],
                                        cwd=self.out, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

            frame = Frame(fname=fname, ts_in=timestamp, ts_out=ts_out)
            self.frames[timestamp] = frame
            self.workq.task_done()

    def make_visible(self, tree, timestamp):
        for e in tree.findall("svg:g", namespaces):
            if ("timestamp" in e.attrib and
               float(e.attrib["timestamp"]) <= timestamp):
                style = e.attrib["style"].split(";")
                style.remove("visibility:hidden")
                e.attrib["style"] = ";".join(style)
            else:
                tree.remove(e)

    def generate_concat(self):
        f = open(os.path.join(self.out, "concat.txt"), "w")
        for t in self.timestamps[0:-1]:
            frame = self.frames[t]
            f.write("file '{}'\n".format(frame.fname))
            f.write("duration {:f}\n".format(frame.ts_out-frame.ts_in))
        f.write("file '{}'\n".format(self.frames[self.timestamps[-2]].fname))
        f.close()

    def render_slides(self):
        result = subprocess.run(["ffmpeg", "-f", "concat", "-i", "concat.txt",
                                 "-pix_fmt", "yuv420p", "-y",
                                 "-vf", "scale=-2:720",
                                 "slides.mp4"],
                                cwd=self.out, stderr=subprocess.PIPE)

def main():
    parser = argparse.ArgumentParser(description='Scrape Big Blue Button')
    parser.add_argument('host', help="Hostname or full Meeting URL")
    parser.add_argument('id', help="Meeting id", nargs='?')
    parser.add_argument('--no-webcam', action='store_true',
                        help="Don't scrape webcam")
    parser.add_argument('--no-deskshare', action='store_true',
                        help="Don't scrape deskshare")
    parser.add_argument('--force', action='store_true',
                        help="Force download, normally uses files from disk")

    args = parser.parse_args()
    host = args.host
    meeting_id = args.id

    # If only one parameter is given, assume it is a full meeting URL and
    # extract host and meeting_id
    if meeting_id is None:
        url = urlparse(host)
        host = url.netloc
        if host is None:
            print("!! Bad meeting URL. Either specify hostname and meeting id"
                  " or the full URL of the recording")
            return 1
        qs = parse_qs(url.query)
        if "meetingId" not in qs:
            print("!! No meeting id given, and no meeting id found in URL")
            return 1
        meeting_id = qs["meetingId"][0]
    else:
        print("ii Usage of <host> <id> arguments is deprecated. "
              "Use <meeting url> as single argument instead.")

    try:
        subprocess.run(["ffmpeg", "-h"],
                       stderr=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL)
    except OSError:
        print("!! ffmpeg not found. Please install it and make sure it is"
              " available in your PATH.")
        return 1

    try:
        subprocess.run(["inkscape", "--help"],
                       stderr=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL)
    except OSError:
        print("!! inkscape not found. Please install it and make sure it is"
              "available in your PATH.")
        return 1

    scrape = Scrape(host, meeting_id)
    print("++ Scrape from server")
    scrape.create_output_dir()
    scrape.fetch_shapes(args.force)
    scrape.fetch_images(None, args.force)
    scrape.fetch_image(args.force)
    if not args.no_webcam and scrape.fetch_webcams(args.force):
        print("++ Stored webcams file")
    if not args.no_deskshare and scrape.fetch_deskshare(args.force):
        print("++ Stored desk sharing file")
    print("++ Generate frames")
    scrape.read_timestamps()
    scrape.generate_frames(args.force)
    scrape.generate_concat()
    print("++ Render slides.mp4")
    scrape.render_slides()

if __name__ == "__main__":
    main()
