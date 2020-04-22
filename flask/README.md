openvino运行依赖的ld可以放到:

'''
cat /etc/ld.so.conf.d/openvino.conf 
/home/yt/intel/openvino_2020.1.023/deployment_tools/ngraph/lib
/opt/intel/opencl
/home/yt/intel/openvino_2020.1.023/deployment_tools/inference_engine/external/hddl/lib
/home/yt/intel/openvino_2020.1.023/deployment_tools/inference_engine/external/gna/lib
/home/yt/intel/openvino_2020.1.023/deployment_tools/inference_engine/external/mkltiny_lnx/lib
/home/yt/intel/openvino_2020.1.023/deployment_tools/inference_engine/external/tbb/lib
/home/yt/intel/openvino_2020.1.023/deployment_tools/inference_engine/lib/intel64
'''
