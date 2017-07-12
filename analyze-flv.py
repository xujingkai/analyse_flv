import sys, getopt
import threading
import Queue
import socket
import signal
import time
import os
from struct import *

def parse_uri(string):
    tmp = string
    if tmp[0:7] != "http://":
        print "please input the correct address"
        exit()
    hostname, uri = tmp[7:].split('/', 1)
    ip = socket.gethostbyname(hostname)
    return ip, hostname, uri

def get_connect(string, port):
    try:
        ip, hostname, uri = parse_uri(string)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, int(port)))    
    except:
        print "connect error"
        exit()

    message = "GET /%s HTTP/1.1\r\nHost: %s\r\nConnection: Close\r\n\r\n" %(uri, hostname)
    s.send(message)
    print'connect success\nremote ip:%s' %(ip)

    return s

def parse_script_data(buf):
    l =[]
    amf1_type = unpack('B', buf[0])
    if amf1_type[0] == 2:
        amf1_len = unpack('>I', '\x00' + '\x00' + buf[1:3])
        string = ''.join(buf[3: 3 + amf1_len[0]])
        amf1_str = "\t\t AMF1: %s\n" %(string)
        l.append(amf1_str)
        buf = buf[3 + amf1_len[0]:]

    amf2_type = unpack('B', buf[0])
    if amf2_type[0] == 8:
        amf2_array_num = unpack('>I', buf[1:5])
        buf = buf[5:]
        n = 0
        while n < amf2_array_num[0]:
            amf2_array_len = unpack('>I', '\x00' + '\x00' + buf[0:2])
            buf = buf[2:]
            amf2_key = ''.join(buf[:amf2_array_len[0]])
            buf = buf[amf2_array_len[0]:]
            amf2_value_type = unpack('B', buf[0])
            buf = buf[1:]
            value_len = 0
            if amf2_value_type[0] == 0:                             #number
                value_len = 8
                amf2_value = unpack('>d', buf[:value_len])
                amf2_value = str(int(amf2_value[0]))
            
            elif amf2_value_type[0] == 1:                           #bool
                value_len = 1
                amf2_value = unpack('?', buf[:value_len])
                amf2_value = str(amf2_value[0])
            
            elif amf2_value_type[0] == 2:                           #string 
                len = unpack('>I', '\x00' + '\x00' + buf[:2])
                value_len = 2 + len[0]
                amf2_value = ''.join(buf[2:value_len])   
            
            elif amf2_value_type[0] == 5:                           #null
                value_len = 0
            amf2_str = "\t\t %s:%s\n" %(amf2_key, amf2_value)
            l.append(amf2_str)
            buf = buf[value_len:]
            n += 1

    elif amf2_type[0] == 3:
        buf = buf[1:]
        
        while len(buf) > 4:                                        #end with 00 00 00 09 
            amf2_key_len = unpack('>I', '\x00' + '\x00' + buf[0:2])
            amf2_key = ''.join(buf[2:amf2_key_len[0]])
            buf = buf[2 + amf2_key_len[0]:]
            amf2_value_type = unpack('B', buf[0])
            buf = buf[1:]
            value_len = 0
            if amf2_value_type[0] == 0:                             #number
                value_len = 8
                amf2_value = unpack('>d', buf[:value_len])
                amf2_value = str(int(amf2_value[0]))

            elif amf2_value_type[0] == 1:                           #bool
                value_len = 1
                amf2_value = unpack('?', buf[:value_len])
                amf2_value = str(amf2_value[0])
            
            elif amf2_value_type[0] == 2:                           #string 
                len = unpack('>I', '\x00' + '\x00' + buf[:2])
                value_len = 2 + len[0]
                amf2_value = ''.join(buf[2:value_len])   
            
            elif amf2_value_type[0] == 5:                           #null
                value_len = 0
            l.append(amf2_str)
            buf = buf[value_len:]

    string = ''.join(l)
    return string 


def parse_video_data(buf):
    l = []
    string = ""
    byte = buf[0]
    get_char_bit = lambda char, n: (char >> (8-n)) & 1 #high to low  1-8
    byte = bytearray(byte)
    result =[]
    for char in byte:
        for i in range(1, 9):
            result.append(get_char_bit(char, i))

    flag = (result[0] << 3 )+ (result[1] << 2) + (result[2] << 1) + result[3]
    frame_type = [
                  (1, "\t\t frame type: keyframe(for AVC, a seekable frame)\n"),
                  (2, "\t\t frame type: inter frame(for AVC, a nonseekable frame)\n"),
                  (3, "\t\t frame type: disposable inter frame(H.263 only)\n"),
                  (4, "\t\t frame type: generated keyframe(reserved for server use)\n"),
                  (5, "\t\t frame type: video info/command frame\n")
                 ]
    item = dict(frame_type)
    string = item[flag]
    l.append(string)

    flag = (result[4] << 3) + (result[5] << 2) + (result[6] << 1) + result[7]
    codec_type = [(1, "\t\t video codec type: JPEG\n"),
                  (2, "\t\t video codec type: Sorenson H.263\n"),
                  (3, "\t\t video codec type: Screen video\n"),
                  (4, "\t\t video codec type: On2 VP6\n"),
                  (5, "\t\t video codec type: On2 Vp6 with alpha channel\n"),
                  (6, "\t\t video codec type: Screen Video version 2\n"),
                  (7, "\t\t video codec type: video codec type: AVC\n")
                ]
    item = dict(codec_type)
    string = item[flag]

    l.append(string)
    string = ''.join(l)   
    return string

def parse_audio_data(buf):
    l = []
    string = ""
    aac_info = ""
    byte = buf[0]
    get_char_bit = lambda char, n: (char >> (8-n)) & 1              
    byte = bytearray(byte)
    result =[]
    for char in byte:
        for i in range(1, 9):
            result.append(get_char_bit(char, i))

    flag = (result[0] << 3) + (result[1] << 2) + (result[2] << 1) + result[3]
    acodec_type = [(0, "\t\t audio codec type: Linear PCM, platform endian\n"),
                   (1, "\t\t audio codec type: ADPCM\n"),
                   (2, "\t\t audio codec type: MP3\n"),
                   (3, "\t\t audio codec type: Linear PCM, little endian\n"),
                   (4, "\t\t audio codec type: Nellymoser 16-kHz mono\n"),
                   (5, "\t\t audio codec type: Nellymoser 8-kHz mono\n"),
                   (6, "\t\t audio codec type: Nellymoser\n"),
                   (7, "\t\t audio codec type: G.711 A-law logarithmic PCM\n"),
                   (8, "\t\t audio codec type: G.711 mu-law logarithmic PCM\n"),
                   (9, "\t\t audio codec type: reserved\n"),
                   (10, "\t\t audio codec type: AAC\n"),
                   (14, "\t\t audio codec type: MP3 8-Khz\n"),
                   (15, "\t\t audio codec type: Device-specific sound\n")
                 ]
    item = dict(acodec_type)
    string = item[flag]
    l.append(string)

    flag = (result[4] << 1) + result[5]
    smp_rate = [(0, "\t\t Audio Sample Rate: 5.5kHz\n"),
                (1, "\t\t Audio Sample Rate: 11KHz\n"),
                (2, "\t\t Audio Sample Rate: 22KHz\n"),
                (3, "\t\t Audio Sample Rate: 44KHz\n")]
    item = dict(smp_rate)
    string = item[flag]
    l.append(string)
    
    flag = int(result[6])
    if flag == 0:
        string = "\t\t Audio sampling accuracy: 8bits\n"
    elif flag == 1:
        string = "\t\t Audio sampling accuracy: 16bits\n"
    l.append(string)

    flag = int(result[7])
    if flag == 0:
        string = "\t\t Audio Type: sndMono\n"
    elif flag == 1:
        string = "\t\t Audio Type: sndStereo\n"
    l.append(string)

    string = ''.join(l)
    return string 

def parse_flvHeader_data(buf):
    string = ""
    l = []
    
    flvHeader = ''.join(buf[0:13])
    signature = unpack('ccc', flvHeader[0:3])
    version = unpack('b', flvHeader[3])
    strSignature = ''.join(signature)
    
    try:
        if strSignature == 'FLV':
            string = "\t\t<---flv Header--->"
            l.append(string)
            string = "\t\tsignature:%s\n" %(strSignature)
            l.append(string)
            string = "\t\tversion: %s\n" %(version[0])
            l.append(string)
        else:
            print ">>>>>>>>>>>>not an flv stream <<<<<<<<<<<<"
            print "[*] please confirm the url is correct"
            os.kill(os.getpid(), signal.SIGTERM)
    
            audiomask = 0x04
            videomask = 0x01
            hasAudio = unpack('B', flvHeader[4])[0] & audiomask
            hasVideo = unpack('B', flvHeader[4])[0] & videomask
            if hasAudio == audiomask:
                string = "\t\thasAudio\n"
                l.append(string)
            if hasVideo == videomask:
                string = "\t\thasVideo\n"
                l.append(string)
            headerSize = unpack('>I', flvHeader[5:9])
            string = "\t\theadersize:%s\n" %(headerSize[0])
            l.append(string)
    except:
        print "[*]parse flv header error"
        os.kill(os.getpid(), SIGTERM)

    string = ''.join(string)
    return string 

class Recv(threading.Thread):
    def __init__(self, work_queue, socket):
        super(Recv, self).__init__()
        self.work_queue = work_queue
        self.socket = socket

    def run(self):
        buf = self.socket.recv(1024)
        CRLF = '\r\n\r\n'
        index = buf.index(CRLF)
        last = buf[index+4:]
        self.work_queue.put(last)
        while True:
            buf = self.socket.recv(1024)
            self.work_queue.put(buf)

class Parse(threading.Thread):
    def __init__(self, work_queue, file):
        super(Parse, self).__init__()
        self.work_queue = work_queue
        self.file = file 

    def run(self):
        string = ""
        buf = []
        tmp = self.work_queue.get()
        buf += tmp
        HeaderStr = parse_flvHeader_data(buf)
        buf = buf[13:]       
        index = 0

        while 1:
            l = []
            while len(buf) < 11:
                tmp = self.work_queue.get()
                buf += tmp

            TagHeader = ''.join(buf[0:11])
            buf = buf[11:]
            tagType = unpack('B', TagHeader[0])
            dataSize = unpack('>I', '\x00' + TagHeader[1:4])
            timeStamp = unpack('>I', TagHeader[4:8])
            streamId = unpack('>I','\x00' + TagHeader[8:11])
            size = dataSize[0]
            while len(buf) < size:
                tmp = self.work_queue.get()
                buf += tmp

            metaTagData = ''.join(buf[:size])
            buf = buf[size:]
            body_string = ""
            type_str = ""
            if tagType[0] == 18:
                type_str = "(script data) \n"
                body_string = parse_script_data(metaTagData)
                metaString = body_string
            elif tagType[0] == 9:
                type_str = "(video tag)\n"
                body_string = parse_video_data(metaTagData)
            elif tagType[0] == 8:
                type_str = "(audio tag)\n"
                body_string = parse_audio_data(metaTagData)
            else:
                print "unkown tag type"
                os.kill(os.getpid(), SIGTERM)

            string = "tag index: %d\n" %(index)
            l.append(string)
            string = "\t <------Tag Header-------->  "
            l.append(string)
            l.append(type_str)
            string = "\t\t dataSize: %d\n" %(dataSize[0])
            l.append(string)
            string = "\t\t timeStamp: %d\n" %(timeStamp[0])
            l.append(string)
            string = "\t\t streamId: %d\n" %(streamId[0])
            l.append(string)
            string = "\t [ ******** Body_Data info ******** ]\n"
            l.append(string)
            l.append(body_string)
            while len(buf) < 4:
                tmp = self.work_queue.get()
                buf += tmp
            
            preTagSize = ''.join(buf[:4])
            buf = buf[4:]
            nPreTagSize = unpack('>I',preTagSize)
            tag_string = ''.join(l)
            index += 1
            
            self.file.write(tag_string)

def sig_handler(sig):
    exit()

def usage():
    print '-p port\n' \
          '-i address\n' \
          '-f file'  
    print '<----examples:----->\n' \
          'python analyze-flv.py -p 80 -f 1.log - i http://server/live/test1.flv'
    exit()

def main():
    global strat_time
    address = ""  
    port = ""
    file_name = ""
    try:
        options, args = getopt.getopt(sys.argv[1:], "hi:p:f:s:", 
            ["address=", "port=", "file_name="])
        for name, value in options:
            if name in ('-i'):
              address = value
            elif name in ('-p'):
              port = value
            elif name in ('-f'):
              file_name = value
    except:
        print "opt error"

    if address == "" or port == "" or file_name == "":
        usage()
        exit()

    signal.signal(signal.SIGINT, sig_handler)
    s = get_connect(address, port)
    file = open(file_name, 'w+') 
    work_queue = Queue.Queue()
    threads=[]
    recv = Recv(work_queue, s)
    threads.append(recv)
    parse = Parse(work_queue, file)
    threads.append(parse)
    for t in threads:
        t.setDaemon(True)
        t.start()
    while True:
        time.sleep(1)
        
if __name__ == "__main__":
    main()
    
