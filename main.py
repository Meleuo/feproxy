# -*- coding: utf-8 -*-
import requests
from flask import Flask, Response, redirect, request
from requests.exceptions import (
    ChunkedEncodingError,
    ContentDecodingError, ConnectionError, StreamConsumedError)
from requests.utils import (
    stream_decode_response_unicode, iter_slices, CaseInsensitiveDict)
from urllib3.exceptions import (
    DecodeError, ReadTimeoutError, ProtocolError)
from urllib.parse import quote

size_limit = 1024 * 1024 * 1024 * 999  # 允许的文件大小，默认999GB，相当于无限制了 https://github.com/hunshcn/gh-proxy/issues/8

HOST = '0.0.0.0'  # 监听地址，建议监听本地然后由web服务器反代
PORT =  50200  # 监听端口

black_list = []
app = Flask(__name__)
CHUNK_SIZE = 1024 * 10
requests.sessions.default_headers = lambda: CaseInsensitiveDict()

@app.route('/')
def index():
    # 简单的hello world页面或者首页信息
    return 'This is a simple proxy service.'

@app.route('/favicon.ico')
def icon():
    # 处理favicon的请求，可以返回一个默认的图标
    return Response('', content_type='image/vnd.microsoft.icon')


def iter_content(self, chunk_size=1, decode_unicode=False):
    def generate():
        # Special case for urllib3.
        if hasattr(self.raw, 'stream'):
            try:
                for chunk in self.raw.stream(chunk_size, decode_content=False):
                    yield chunk
            except ProtocolError as e:
                raise ChunkedEncodingError(e)
            except DecodeError as e:
                raise ContentDecodingError(e)
            except ReadTimeoutError as e:
                raise ConnectionError(e)
        else:
            # Standard file-like object.
            while True:
                chunk = self.raw.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        self._content_consumed = True

    if self._content_consumed and isinstance(self._content, bool):
        raise StreamConsumedError()
    elif chunk_size is not None and not isinstance(chunk_size, int):
        raise TypeError("chunk_size must be an int, it is instead a %s." % type(chunk_size))
    # simulate reading small chunks of the content
    reused_chunks = iter_slices(self._content, chunk_size)

    stream_chunks = generate()

    chunks = reused_chunks if self._content_consumed else stream_chunks

    if decode_unicode:
        chunks = stream_decode_response_unicode(chunks, self)

    return chunks



#@app.route('/<path:u>', methods=['GET', 'POST'])
@app.route('/<path:u>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def handler(u):
    #print('Url-->',u)
    u = u if u.startswith('http') else 'https://' + u
    if u.rfind('://', 3, 9) == -1:
        u = u.replace('s:/', 's://', 1)  # uwsgi会将//传递为/
    u = u.replace('/info/refs?service=git-upload-pack', '')  # uwsgi会将//传递为/a
    u = u.replace('/info/refs', '')  # uwsgi会将//传递为/a
    print('Url-->',u)
    # 打印全部参数
    
    
    
    #print(request.data)
    #print(request.args)

    for i in black_list:
        if i in u:
            return Response('Invalid input.', status=403)

    headers = {}
    r_headers = dict(request.headers)
    if 'Host' in r_headers:
        r_headers.pop('Host')
    try:
        url = u + request.url.replace(request.base_url, '', 1)
        if url.startswith('https:/') and not url.startswith('https://'):
            url = 'https://' + url[7:]
        r = requests.request(method=request.method, url=url, data=request.data, headers=r_headers, stream=True, allow_redirects=True)
        headers = dict(r.headers)
    
        if 'Content-length' in r.headers and int(r.headers['Content-length']) > size_limit:
            return redirect(u + request.url.replace(request.base_url, '', 1))

        def generate():
            for chunk in iter_content(r, chunk_size=CHUNK_SIZE):
                yield chunk

        return Response(generate(), headers=headers, status=r.status_code)
    except Exception as e:
        headers['content-type'] = 'text/html; charset=UTF-8'
        return Response('Invalid input.', status=403)
        #return Response('server error ' + str(e), status=500, headers=headers)

if __name__ == '__main__':
    import time
    while 1:
        try:
            app.run(host=HOST, port=PORT, threaded=True)
        except Exception as e:
            print(e)
        time.sleep(2)
