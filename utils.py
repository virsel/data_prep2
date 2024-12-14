from pathlib import Path
import pandas as pd
from datetime import datetime

script_path = Path(__file__).parent.absolute()
metrics_path = str(script_path / 'input/fault_suffering/{}/metric/{pod}_metric.csv')

def parse_custom_timestamp(timestamp_str):
    # Split the timestamp and take the first part (before additional UTC info)
    base_timestamp = timestamp_str.split(' +0000')[0]
    return pd.to_datetime(base_timestamp, format='%Y-%m-%d %H:%M:%S.%f')

def get_podmetrics(expected_moreoften, actual_moreoften, abnormal_date, normal_date):
    day = abnormal_date.split()[0]
    target_time = pd.to_datetime(abnormal_date)
    normal_time = pd.to_datetime(normal_date)
    affected_pods = set()
    res = dict()
    
    for pattern in expected_moreoften:
        affected_pods.add(pattern['pod'])
    for pattern in actual_moreoften:
        affected_pods.add(pattern['pod']) 
        
    for pod in affected_pods:
        df = pd.read_csv(metrics_path.format(day, pod=pod))  
        df.Time = df.Time.apply(parse_custom_timestamp)      
        
        # target 
        df_res_target = df[df['Time'].dt.floor('T') == target_time][['CpuUsageRate(%)', 'MemoryUsageRate(%)', 'PodClientLatencyP90(s)', 'PodServerLatencyP90(s)', 'NodeCpuUsageRate(%)', 'NodeMemoryUsageRate(%)']]
        df_res_target = df_res_target.select_dtypes(include=['float64', 'float32']).round(3)
        
        # normal
        df_res_normal = df[df['Time'].dt.floor('T') == normal_time][['CpuUsageRate(%)', 'MemoryUsageRate(%)', 'PodClientLatencyP90(s)', 'PodServerLatencyP90(s)', 'NodeCpuUsageRate(%)', 'NodeMemoryUsageRate(%)']]
        df_res_normal = df_res_normal.select_dtypes(include=['float64', 'float32']).round(3)
        df_res_normal = df_res_normal.reset_index(drop=True).loc[0]
        
        dict_res = df_res_target.reset_index(drop=True).loc[0].to_dict()
        
        pod_res_with_diff = {}
        for metric, target_val in dict_res.items():
            normal_val = df_res_normal[metric]

            # Add original value
            pod_res_with_diff[metric] = f"{target_val} {calc_percentage_diff(target_val, normal_val)}"
    
        res[pod] = pod_res_with_diff
        
    return res

# Function to calculate percentage difference and format
def calc_percentage_diff(target_val, normal_val):
    if normal_val == 0:
        return f"(N/A)" if target_val == 0 else "(Inf%)"
    
    diff_percentage = ((target_val - normal_val) / normal_val) * 100
    sign = "+" if diff_percentage >= 0 else ""
    return f"({sign}{diff_percentage:.1f}%)"
    
if __name__ == '__main__':
    abnormal_time = '2020-08-21T00:00:00Z'
    get_podmetrics(abnormal_time)