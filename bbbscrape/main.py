#!/usr/bin/env python3

import requests
import os
import argparse
from xml.etree import ElementTree
from collections import namedtuple
import subprocess

namespaces = {"svg": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}

Image = namedtuple("Image", ["id", "fname", "ts_in", "ts_out"])

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

    def fetch_shapes(self):
        url = "{}/shapes.svg".format(self.baseurl)
        shapes = requests.get(url)
        self.shapes = ElementTree.fromstring(shapes.content)
        open(os.path.join(self.out, "shapes.svg"), "wb").write(shapes.content)

    def fetch_deskshare(self):
        url = "{}/deskshare/deskshare.mp4".format(self.baseurl)
        req = requests.get(url)
        if req.status_code == 200:
           open(os.path.join(self.out, "deskshare.mp4"), "wb").write(req.content)
           return True
        return False

    def fetch_webcams(self):
        url = "{}/video/webcams.mp4".format(self.baseurl)
        req = requests.get(url)
        if req.status_code == 200:
           open(os.path.join(self.out, "webcams.mp4"), "wb").write(req.content)
           return True
        return False

    def fetch_images(self):
        self.images = []
        for e in self.shapes.findall("svg:image", namespaces):
            href = e.attrib["{http://www.w3.org/1999/xlink}href"]
            fname = os.path.basename(href)
            url = "{}/{}".format(self.baseurl, href)
            image = requests.get(url)
            open(os.path.join(self.out, fname), "wb").write(image.content)
            self.images.append(Image(id=e.attrib["id"],
                                     fname=fname,
                                     ts_in=float(e.attrib["in"]),
                                     ts_out=float(e.attrib["out"])))

    def generate_frames(self):
        # For now its just the slides
        self.frames = self.images

    def generate_concat(self):
        f = open(os.path.join(self.out, "concat.txt"), "w")
        for frame in self.frames:
            f.write("file '{}'\n".format(frame.fname))
            f.write("duration {:f}\n".format(frame.ts_out-frame.ts_in))
        f.write("file '{}'\n".format(self.frames[-1].fname))
        f.close()

    def render_slides(self):
        subprocess.run(["ffmpeg", "-f", "concat", "-i", "concat.txt", "-pix_fmt", "yuv420p", "-y", "slides.mp4"], cwd=self.out, stderr=subprocess.PIPE)

def main():
    parser = argparse.ArgumentParser(description='Scrape')
    parser.add_argument('host', help="Hostname")
    parser.add_argument('id', help="Meeting id")
    args = parser.parse_args()

    scrape = Scrape(args.host, args.id)
    print("++ Scrape from server")
    scrape.create_output_dir()
    scrape.fetch_shapes()
    scrape.fetch_images()
    if scrape.fetch_webcams():
        print("++ Stored webcams to webcams.mp4")
    if scrape.fetch_deskshare():
        print("++ Store desk sharing to deskshare.mp4")
    print("++ Generate frames")
    scrape.generate_frames()
    scrape.generate_concat()
    print("++ Render slides.mp4")
    scrape.render_slides()
