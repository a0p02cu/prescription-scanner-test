import requests
from os import listdir
from pprint import pprint
from fuzzywuzzy import fuzz
from difflib import SequenceMatcher 
import re
import subprocess


from flask import Flask
import base64
from flask_restful import reqparse, abort, Api, Resource

app = Flask(__name__)
api = Api(app)


parser = reqparse.RequestParser()
parser.add_argument('lines')

def cliner_res():
    subprocess.run(["python3", "clin/cliner", "predict", "--txt", "output.txt","--out", "clin/data/predictions/", "--format", "i2b2", "--model", "clin/models/silver.crf"])
    op = []
    with open('clin/data/predictions/output.con') as f:
        lines = f.readlines()
    for line in lines:
        if line.split('||')[1] == 't="treatment"\n':
            op.append(line.split('||')[0].split('"')[1])
    return op

class Video_recv(Resource):
    def post(self):
        args = parser.parse_args()
        res = args['lines']
        print(res)
        res = res.split('\t')
        with open('output.txt', 'w') as f:
            f.write('\n'.join(res))

        return {'res':cliner_res()}, 201

api.add_resource(Video_recv, '/cliner')

if __name__ == '__main__':
    app.run(debug=True, port=8000, host='0.0.0.0')