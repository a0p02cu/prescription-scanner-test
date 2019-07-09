import requests
from os import listdir
from pprint import pprint
from fuzzywuzzy import fuzz
from difflib import SequenceMatcher 
import re
import subprocess
import multiprocessing
import threading
import usaddress
import glob
import os

from flask import Flask
import base64
from flask_restful import reqparse, abort, Api, Resource

app = Flask(__name__)
api = Api(app)

# parser = reqparse.RequestParser()


subscription_key = "759bb8c5ea6146ccbe5fd58ae2a3bdf4"
assert subscription_key

vision_base_url = "https://eastus.api.cognitive.microsoft.com/vision/v2.0/"
ocr_url = vision_base_url + "ocr"
rec_text = vision_base_url + "recognizeText"
folder = "recv-frames/"

def clean_folder(path=folder):
    contents = glob.glob(path+'*')
    for c in contents:
        os.remove(c)

def vid2frames():
    subprocess.run(["ffmpeg","-i","vid.mp4","-vf","select='eq(pict_type\\,PICT_TYPE_I)'","-vsync","2","-f","image2","extracted-frames/frame-%02d.jpeg"])

class ocrThread (threading.Thread):
    def __init__(self, file): 
        threading.Thread.__init__(self)
        self.file = file
        self.result = {'status':'Running'}

    def run(self):
        image_data = open(folder+self.file, "rb").read()
        headers    = {'Ocp-Apim-Subscription-Key': subscription_key,
                      'Content-Type': 'application/octet-stream'}
        params = {'mode':'Printed'}

        resp = requests.request('post',rec_text, headers=headers, params=params, data=image_data)

        oploc = resp.headers['Operation-Location']
        result = {'status':'Running'}

        while(result['status'] != 'Succeeded'):
            response = requests.request('get',oploc,json=None, data=None, headers=headers, params=None)
            result = response.json()
            try:
                st = result['status']
            except Exception as e:
                result = {'status':'Running'}

        if result['status'] == 'Succeeded':
            result['frame'] = self.file
        self.result = result


def get_lines(res):
    ls = res['recognitionResult']['lines']
    lines = []
    bbox = []
    for line in ls:
        lines.append(line['text'])
        bbox.append(line['boundingBox'])
    return lines, bbox

def common(str1,str2): 
    seqMatch = SequenceMatcher(None,str1,str2)  
    match = seqMatch.find_longest_match(0, len(str1), 0, len(str2)) 
    if (match.size!=0):
        return str1[match.a: match.a + match.size]
    else: 
        return -1

def join_sentences(st1, st2):
    comm = common(st1, st2)
    res = st1.split(comm)[0] + comm +st2.split(comm)[1]
    return res

def process_lines(list1, list2):
    line_res = []
    for line1 in list1:
        for line2 in list2:
            val = fuzz.ratio(line1, line2)
            if val > 70 and val<100:
                line_res.append(join_sentences(line1, line2))
    return line_res+list1

def find_rxno(string):
    regex = r"rx.*[0-9]{7}"
    rxno = re.findall(regex, string, re.IGNORECASE)
    rxno = re.findall(r"[0-9]{7}", rxno[0])[0]
    return rxno

def process_result(res):
    sres  = sorted(res)
    i=0
    while(i<len(sres)-1):
        val = fuzz.ratio(sres[i],sres[i+1])
        if val>50:
            del(sres[i+1])
        else:
            i+=1
    return sres

def find_address(res):
    for add in res:
        if usaddress.tag(add)[1] is not 'Ambiguous':
            return add
    return None

def cliner_res():
    subprocess.run(["python3", "clin/cliner", "predict", "--txt", "output.txt","--out", "clin/data/predictions/", "--format", "i2b2", "--model", "clin/models/silver.crf"])
    op = []
    with open('clin/data/predictions/output.con') as f:
        lines = f.readlines()
    for line in lines:
        if line.split('||')[1] == 't="treatment"\n':
            op.append(line.split('||')[0].split('"')[1])
    return op

def cliner_call(res):
    cliner_url = "http://localhost:8000/cliner"
    data = {"lines":res}
    resp = requests.post(cliner_url, data=data)
    return resp.json()

def detect_pharmacy(res):
    return "SAM'S CLUB"

class Frame_recv(Resource):
    def get(self):
        # clean_folder()
        # parser = reqparse.RequestParser()
        # parser.add_argument('task', type=list, location='json')
        # args = parser.parse_args()
        # frame_string = args['task']
        # ctr = 1
        # for string in frame_string:
            # decoded_string = base64.b64decode(string)
            # new_video_path = folder+'frame'+"{0:0=2d}".format(ctr)+'.jpeg'
            # ctr+=1
            # with open(new_video_path, "wb") as image_file2:
                # image_file2.write(decoded_string);
        files = sorted(listdir(folder))
        print(files)
        threads = [ocrThread(file) for file in files]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
        frame_results = [thread.result for thread in threads]
        for r in frame_results:
            try:
                fl = r['frame']           
            except Exception as e:
                frame_results.remove(r)

        frame_results = sorted(frame_results, key=lambda k: k['frame'])

        line_list = []
        for i in range(len(frame_results)):
            l, box = get_lines(frame_results[i])
            line_list.append(l)

        with open('lines.txt','w') as f:
            f.write(str(line_list))

        res = line_list[0]
        for i in range(1, len(line_list)):
            res = process_lines(res, line_list[i])
            res = list(set(res))
        res = process_result(res)
        pprint(res)
        with open('output.txt', 'w') as f:
            f.write('\n'.join(res))

        return {'rxno':find_rxno(' '.join(res)), 'address':find_address(res),
                'pharmacy':detect_pharmacy(res),'cliner':cliner_call('\t'.join(res))}, 201


class Video_recv(Resource):
    def get(self):
        clean_folder("extracted-frames/")
        # parser = reqparse.RequestParser()
        # parser.add_argument('task')
        # args = parser.parse_args()
        # encoded_string = args['task']
        # decoded_string = base64.b64decode(encoded_string)
        new_video_path = 'vid.mp4'
        # with open(new_video_path, "wb") as image_file2:
        #     image_file2.write(decoded_string);
        vid2frames()
        files = sorted(listdir(folder))
        print(files)
        threads = [ocrThread(file) for file in files]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
        frame_results = [thread.result for thread in threads]
        for r in frame_results:
            try:
                fl = r['frame']           
            except Exception as e:
                frame_results.remove(r)

        # frame_results = sorted(frame_results, key=lambda k: k['frame'])

        frame_results = sorted(frame_results, key=lambda k: k['frame'])

        line_list = []
        for i in range(len(frame_results)):
            l, box = get_lines(frame_results[i])
            line_list.append(l)

        with open('lines.txt','w') as f:
            f.write(str(line_list))

        res = line_list[0]
        for i in range(1, len(line_list)):
            res = process_lines(res, line_list[i])
            res = list(set(res))
        res = process_result(res)
        pprint(res)
        with open('output.txt', 'w') as f:
            f.write('\n'.join(res))

        return {'rxno':find_rxno(' '.join(res)), 'address':find_address(res),
                'pharmacy':detect_pharmacy(res),'cliner':cliner_call('\t'.join(res))}, 201

api.add_resource(Video_recv, '/video')
api.add_resource(Frame_recv, '/frames')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
