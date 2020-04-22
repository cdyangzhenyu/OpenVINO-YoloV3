import sys, os, cv2, time, heapq, argparse
from PIL import Image, ImageFont, ImageDraw
import numpy as np, math
try:
    from armv7l.openvino.inference_engine import IENetwork, IEPlugin
except:
    from openvino.inference_engine import IENetwork, IEPlugin
import multiprocessing as mp
from time import sleep
import threading

yolo_scale_13 = 13
yolo_scale_26 = 26
yolo_scale_52 = 52

classes = 19
coords = 4
num = 3
anchors = [10,13,16,30,33,23,30,61,62,45,59,119,116,90,156,198,373,326]

LABELS = ("apple_black_rot", "apple_cedar_rust", "apple_healthy", "apple_scab", "cherry_healthy",
          "cherry_sour_powdery_mildew", "grape_black_rot", "grape_blight", "grape_esca", "grape_healthy",
          "peach_bacterial_spot", "peach_healthy", "pepper_bacterial_spot", "pepper_healthy", "potato_eb",
          "potato_healthy", "potato_lb", "strawberry_Leaf_scorch", "strawberry_healthy")

label_text_color = (255, 255, 0)
label_background_color = (125, 175, 75)
box_color = (255, 128, 0)
box_thickness = 2

processes = []

fps = ""
detectfps = ""
framecount = 0
detectframecount = 0
time1 = 0
time2 = 0
lastresults = None

DESCRIPTION = {"strawberry_healthy": "这株草莓很健康。", 
               "strawberry_Leaf_scorch": "这株草莓得了叶焦病，草莓叶焦（Leaf Scorch）是由真菌感染\n"
                                         "引起的，真菌感染会影响草莓种植的叶子。这种真菌称为双翅龙，\n"
                                         "感染这种真菌的草莓叶子最初会在叶片顶部出现紫色小斑点，随\n"
                                         "着时间的流逝，斑点将继续变大、变暗。严重的情况下，黑点甚至\n"
                                         "可能覆盖草莓植物叶片的整个部分，这可能导致整个叶片完全干燥\n"
                                         "并从植物上掉下来。这种由真菌引起的草莓病害对草莓作物本身的\n"
                                         "质量影响不大。\n"
                                         "防治方法：保持通风、清洁卫生、避免土壤过涝",
               "cherry_healthy": "这株樱桃很健康。",
               "cherry_sour_powdery_mildew": "樱桃白粉病（Powdery Mildew）是一种农作物常见的病害，\n"
                                             "感染之后会在叶片出现一些白色状的粉状霉层，在一般的情\n"
                                             "况下叶片背面的白色粉状霉层比正面的多，然后再慢慢蔓延\n"
                                             "到果实，从而使果实的果面也出现白色粉状霉层，同时果实\n"
                                             "会出现表皮枯死、硬化、龟裂等症状，从而使樱桃出生早衰\n"
                                             "的现象，降低产量。\n"
                                             "防治方法：\n"
                                             "  1、发病期喷洒0.3°Be石硫合剂或25％粉锈宁3000倍液、\n"
                                             "70％甲基硫菌灵可湿性粉剂1500倍液1-2次。\n"
                                             "  2、秋后清理果园，扫除落叶，集中烧毁。一般对于樱桃白\n"
                                             "粉病的防治建议以预防为主，因为预防好了，能有效减少白\n"
                                             "粉病的发生，这样可以尽量避免使用农药进行治疗，从而起\n"
                                             "到减少樱桃果实中的农药残留量的作用，保证了樱桃果实的\n"
                                             "品质，获得好效益。"}

def paint_chinese_opencv(im,chinese,position,fontsize,color):#opencv输出中文
    img_PIL = Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB))# 图像从OpenCV格式转换成PIL格式
    font = ImageFont.truetype('simhei.ttf',fontsize,encoding="utf-8")
    #color = (255,0,0) # 字体颜色
    #position = (100,100)# 文字输出位置
    draw = ImageDraw.Draw(img_PIL)
    draw.text(position,chinese,font=font,fill=color)# PIL图片上打印汉字 # 参数1：打印坐标，参数2：文本，参数3：字体颜色，参数4：字体
    img = cv2.cvtColor(np.asarray(img_PIL),cv2.COLOR_RGB2BGR)# PIL图片转cv2 图片
    return img

def EntryIndex(side, lcoords, lclasses, location, entry):
    n = int(location / (side * side))
    loc = location % (side * side)
    return int(n * side * side * (lcoords + lclasses + 1) + entry * side * side + loc)


class DetectionObject():
    xmin = 0
    ymin = 0
    xmax = 0
    ymax = 0
    class_id = 0
    confidence = 0.0

    def __init__(self, x, y, h, w, class_id, confidence, h_scale, w_scale):
        self.xmin = int((x - w / 2) * w_scale)
        self.ymin = int((y - h / 2) * h_scale)
        self.xmax = int(self.xmin + w * w_scale)
        self.ymax = int(self.ymin + h * h_scale)
        self.class_id = class_id
        self.confidence = confidence


def IntersectionOverUnion(box_1, box_2):
    width_of_overlap_area = min(box_1.xmax, box_2.xmax) - max(box_1.xmin, box_2.xmin)
    height_of_overlap_area = min(box_1.ymax, box_2.ymax) - max(box_1.ymin, box_2.ymin)
    area_of_overlap = 0.0
    if (width_of_overlap_area < 0.0 or height_of_overlap_area < 0.0):
        area_of_overlap = 0.0
    else:
        area_of_overlap = width_of_overlap_area * height_of_overlap_area
    box_1_area = (box_1.ymax - box_1.ymin)  * (box_1.xmax - box_1.xmin)
    box_2_area = (box_2.ymax - box_2.ymin)  * (box_2.xmax - box_2.xmin)
    area_of_union = box_1_area + box_2_area - area_of_overlap
    retval = 0.0
    if area_of_union <= 0.0:
        retval = 0.0
    else:
        retval = (area_of_overlap / area_of_union)
    return retval


def ParseYOLOV3Output(blob, resized_im_h, resized_im_w, original_im_h, original_im_w, threshold, objects):

    out_blob_h = blob.shape[2]
    out_blob_w = blob.shape[3]

    side = out_blob_h
    anchor_offset = 0

    if side == yolo_scale_13:
        anchor_offset = 2 * 6
    elif side == yolo_scale_26:
        anchor_offset = 2 * 3
    elif side == yolo_scale_52:
        anchor_offset = 2 * 0

    side_square = side * side
    output_blob = blob.flatten()

    for i in range(side_square):
        row = int(i / side)
        col = int(i % side)
        for n in range(num):
            obj_index = EntryIndex(side, coords, classes, n * side * side + i, coords)
            box_index = EntryIndex(side, coords, classes, n * side * side + i, 0)
            scale = output_blob[obj_index]
            if (scale < threshold):
                continue
            x = (col + output_blob[box_index + 0 * side_square]) / side * resized_im_w
            y = (row + output_blob[box_index + 1 * side_square]) / side * resized_im_h
            height = math.exp(output_blob[box_index + 3 * side_square]) * anchors[anchor_offset + 2 * n + 1]
            width = math.exp(output_blob[box_index + 2 * side_square]) * anchors[anchor_offset + 2 * n]
            for j in range(classes):
                class_index = EntryIndex(side, coords, classes, n * side_square + i, coords + 1 + j)
                prob = scale * output_blob[class_index]
                if prob < threshold:
                    continue
                obj = DetectionObject(x, y, height, width, j, prob, (original_im_h / resized_im_h), (original_im_w / resized_im_w))
                objects.append(obj)
    return objects


def camThread(LABELS, results, frameBuffer, camera_width, camera_height, vidfps):
    global fps
    global detectfps
    global lastresults
    global framecount
    global detectframecount
    global time1
    global time2
    global cam
    global window_name

    cam = cv2.VideoCapture(0)
    if cam.isOpened() != True:
        print("USB Camera Open Error!!!")
        sys.exit(0)
    cam.set(cv2.CAP_PROP_FPS, vidfps)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
    window_name = "USB Camera"
    wait_key_time = 1

    #cam = cv2.VideoCapture("data/input/testvideo4.mp4")
    #camera_width = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
    #camera_height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
    #frame_count = int(cam.get(cv2.CAP_PROP_FRAME_COUNT))
    #window_name = "Movie File"
    #wait_key_time = int(1000 / vidfps)

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    while True:
        t1 = time.perf_counter()

        # USB Camera Stream Read
        s, color_image = cam.read()
        if not s:
            continue
        if frameBuffer.full():
            frameBuffer.get()

        height = color_image.shape[0]
        width = color_image.shape[1]
        frameBuffer.put(color_image.copy())

        if not results.empty():
            objects = results.get(False)
            detectframecount += 1

            for obj in objects:
                if obj.confidence < 0.2:
                    continue
                label = obj.class_id
                confidence = obj.confidence
                if confidence > 0.2:
                    label_text = LABELS[label] + " (" + "{:.1f}".format(confidence * 100) + "%)"
                    cv2.rectangle(color_image, (obj.xmin, obj.ymin), (obj.xmax-10, obj.ymax-10), box_color, box_thickness)
                    cv2.putText(color_image, label_text, (obj.xmin, obj.ymin - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, label_text_color, 1)
                    if DESCRIPTION.get(LABELS[label], None):
                        color_image = paint_chinese_opencv(color_image, DESCRIPTION[LABELS[label]], (obj.xmin, obj.ymin + 50), 16, (255,255,0))
            lastresults = objects
        else:
            if not isinstance(lastresults, type(None)):
                for obj in lastresults:
                    if obj.confidence < 0.2:
                        continue
                    label = obj.class_id
                    confidence = obj.confidence
                    if confidence > 0.2:
                        label_text = LABELS[label] + " (" + "{:.1f}".format(confidence * 100) + "%)"
                        cv2.rectangle(color_image, (obj.xmin, obj.ymin), (obj.xmax-10, obj.ymax-10), box_color, box_thickness)
                        cv2.putText(color_image, label_text, (obj.xmin, obj.ymin - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, label_text_color, 1)
                        if DESCRIPTION.get(LABELS[label], None):
                            color_image = paint_chinese_opencv(color_image, DESCRIPTION[LABELS[label]], (obj.xmin, obj.ymin + 50), 16, (255,255,0))
        cv2.putText(color_image, fps,       (width-170,15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (38,0,255), 1, cv2.LINE_AA)
        cv2.putText(color_image, detectfps, (width-170,30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (38,0,255), 1, cv2.LINE_AA)
        cv2.imshow(window_name, cv2.resize(color_image, (width, height)))

        if cv2.waitKey(wait_key_time)&0xFF == ord('q'):
            sys.exit(0)

        ## Print FPS
        framecount += 1
        if framecount >= 15:
            fps       = "(Playback) {:.1f} FPS".format(time1/15)
            detectfps = "(Detection) {:.1f} FPS".format(detectframecount/time2)
            framecount = 0
            detectframecount = 0
            time1 = 0
            time2 = 0
        t2 = time.perf_counter()
        elapsedTime = t2-t1
        time1 += 1/elapsedTime
        time2 += elapsedTime


# l = Search list
# x = Search target value
def searchlist(l, x, notfoundvalue=-1):
    if x in l:
        return l.index(x)
    else:
        return notfoundvalue


def async_infer(ncsworker):

    ncsworker.skip_frame_measurement()

    while True:
        ncsworker.predict_async()


class NcsWorker(object):

    def __init__(self, devid, frameBuffer, results, camera_width, camera_height, number_of_ncs, vidfps):
        self.devid = devid
        self.frameBuffer = frameBuffer
        self.model_xml = "./lrmodels/YoloV3_plant/FP16/yolov3_plant_model.xml"
        self.model_bin = "./lrmodels/YoloV3_plant/FP16/yolov3_plant_model.bin"
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.m_input_size = 416
        self.threshould = 0.7
        self.num_requests = 4
        self.inferred_request = [0] * self.num_requests
        self.heap_request = []
        self.inferred_cnt = 0
        self.plugin = IEPlugin(device="MYRIAD")
        self.net = IENetwork(model=self.model_xml, weights=self.model_bin)
        self.input_blob = next(iter(self.net.inputs))
        self.exec_net = self.plugin.load(network=self.net, num_requests=self.num_requests)
        self.results = results
        self.number_of_ncs = number_of_ncs
        self.predict_async_time = 800
        self.skip_frame = 0
        self.roop_frame = 0
        self.vidfps = vidfps
        self.new_w = int(camera_width * self.m_input_size/camera_width)
        self.new_h = int(camera_height * self.m_input_size/camera_height)

    def image_preprocessing(self, color_image):
        resized_image = cv2.resize(color_image, (self.new_w, self.new_h), interpolation = cv2.INTER_CUBIC)
        canvas = np.full((self.m_input_size, self.m_input_size, 3), 128)
        canvas[(self.m_input_size-self.new_h)//2:(self.m_input_size-self.new_h)//2 + self.new_h,(self.m_input_size-self.new_w)//2:(self.m_input_size-self.new_w)//2 + self.new_w,  :] = resized_image
        prepimg = canvas
        prepimg = prepimg[np.newaxis, :, :, :]     # Batch size axis add
        prepimg = prepimg.transpose((0, 3, 1, 2))  # NHWC to NCHW
        return prepimg


    def skip_frame_measurement(self):
            surplustime_per_second = (1000 - self.predict_async_time)
            if surplustime_per_second > 0.0:
                frame_per_millisecond = (1000 / self.vidfps)
                total_skip_frame = surplustime_per_second / frame_per_millisecond
                self.skip_frame = int(total_skip_frame / self.num_requests)
            else:
                self.skip_frame = 0


    def predict_async(self):
        try:

            if self.frameBuffer.empty():
                return

            self.roop_frame += 1
            if self.roop_frame <= self.skip_frame:
               self.frameBuffer.get()
               return
            self.roop_frame = 0

            prepimg = self.image_preprocessing(self.frameBuffer.get())
            reqnum = searchlist(self.inferred_request, 0)

            if reqnum > -1:
                self.exec_net.start_async(request_id=reqnum, inputs={self.input_blob: prepimg})
                self.inferred_request[reqnum] = 1
                self.inferred_cnt += 1
                if self.inferred_cnt == sys.maxsize:
                    self.inferred_request = [0] * self.num_requests
                    self.heap_request = []
                    self.inferred_cnt = 0
                heapq.heappush(self.heap_request, (self.inferred_cnt, reqnum))

            cnt, dev = heapq.heappop(self.heap_request)

            if self.exec_net.requests[dev].wait(0) == 0:
                self.exec_net.requests[dev].wait(-1)

                objects = []
                outputs = self.exec_net.requests[dev].outputs
                for output in outputs.values():
                    objects = ParseYOLOV3Output(output, self.new_h, self.new_w, self.camera_height, self.camera_width, self.threshould, objects)
                objlen = len(objects)
                for i in range(objlen):
                    if (objects[i].confidence == 0.0):
                        continue
                    for j in range(i + 1, objlen):
                        if (IntersectionOverUnion(objects[i], objects[j]) >= 0.4):
                            objects[j].confidence = 0

                self.results.put(objects)
                self.inferred_request[dev] = 0
            else:
                heapq.heappush(self.heap_request, (cnt, dev))
        except:
            import traceback
            traceback.print_exc()


def inferencer(results, frameBuffer, number_of_ncs, camera_width, camera_height, vidfps):

    # Init infer threads
    threads = []
    for devid in range(number_of_ncs):
        thworker = threading.Thread(target=async_infer, args=(NcsWorker(devid, frameBuffer, results, camera_width, camera_height, number_of_ncs, vidfps),))
        thworker.start()
        threads.append(thworker)

    for th in threads:
        th.join()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-numncs','--numberofncs',dest='number_of_ncs',type=int,default=1,help='Number of NCS. (Default=1)')
    args = parser.parse_args()

    number_of_ncs = args.number_of_ncs
    camera_width = 640
    camera_height = 480
    vidfps = 30

    try:

        mp.set_start_method('forkserver')
        frameBuffer = mp.Queue(10)
        results = mp.Queue()

        # Start detection MultiStick
        # Activation of inferencer
        p = mp.Process(target=inferencer, args=(results, frameBuffer, number_of_ncs, camera_width, camera_height, vidfps), daemon=True)
        p.start()
        processes.append(p)

        sleep(number_of_ncs * 7)

        # Start streaming
        p = mp.Process(target=camThread, args=(LABELS, results, frameBuffer, camera_width, camera_height, vidfps), daemon=True)
        p.start()
        processes.append(p)

        while True:
            sleep(1)

    except:
        import traceback
        traceback.print_exc()
    finally:
        for p in range(len(processes)):
            processes[p].terminate()

        print("\n\nFinished\n\n")
