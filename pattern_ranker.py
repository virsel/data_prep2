import datetime
from data_integrate import *
from pattern_miner import *
import pdb
import time
import tqdm
from config import Config
from datetime import datetime, timedelta

log_path = dirname(__file__) + '/log/' + str(datetime.now().strftime(
    '%Y-%m-%d')) + '_nezha.log'
logger = Logger(log_path, logging.DEBUG, __name__).getlog()


def get_pattern(detete_time, data_path, log_template_miner,topk=30):
    """
    func get_pattern: get pattern at the detete_time
    :parameter
        detete_time  - query data
        construction_data_path  - basedir
        topk - return topk pattern
    :return
        pattern_list
        event_graphs
    """
    date = detete_time.split(" ")[0]
    hour = detete_time.split(" ")[1].split(":")[0]
    min = detete_time.split(" ")[1].split(":")[1]

    trace_file = data_path + "/" + date + \
        "/trace/" + str(hour) + "_" + str(min) + "_trace.csv"
    trace_id_file = data_path + "/" + date + \
        "/traceid/" + str(hour) + "_" + str(min) + "_traceid.csv"
    log_file = data_path + "/" + date + \
        "/log/" + str(hour) + "_" + str(min) + "_log.csv"

    metric_list = get_metric_with_time(detete_time, data_path)
    alarm_list = generate_alarm(metric_list)
    # print(alarm_list)
    # alarm_list = {}
    event_graphs = data_integrate(
        trace_file, trace_id_file, log_file, alarm_list, log_template_miner)
    # file_name = generate_tkg_input(event_graphs)
    # pattern_list = frequent_graph_miner(file_name, topk=topk)
    result_support_list = get_pattern_support(event_graphs)

    return result_support_list, event_graphs, alarm_list


def get_event_depth_pod(normal_event_graphs, event_pair):
    source = int(event_pair.split("_")[0])
    maxdepth = 0
    event_pod = ""

    for normal_event_graph in normal_event_graphs:
        deepth, pod = normal_event_graph.get_deepth_pod(source)
        if deepth > maxdepth:
            maxdepth = deepth
            event_pod = pod

    # logger.info("%s's source %s deepth is %s, pod is %s" %
    #             (event_pair, source, maxdepth, event_pod))

    return maxdepth, event_pod

def get_pattern_ranked_dict(pattern_dict_referenz, pattern_dict_fokus, min_score=0.67):
    score_dict = {}
    for key in pattern_dict_fokus.keys():
        if pattern_dict_fokus[key] > 5:
            if key not in score_dict.keys():
                score_dict[key] = 0
            if key in pattern_dict_referenz.keys():
                score_dict[key] =  (1.0 * pattern_dict_fokus[key]) / \
                    (pattern_dict_fokus[key] + pattern_dict_referenz[key])
                # print(abnormal_pattern_dict[key],
                #       normal_pattern_dict[key], score_dict[key])
            else:
                score_dict[key] = 1.0

    move_list = set()
    for key, value in score_dict.items():
        # only consider score > 0.66, i.e., 1 / 1 + 0.5
        if float(value) < min_score:
            # logger.info("move key %s because score %s < 0.66" % (key, value))
            move_list.add(key)
    for item in move_list:
        score_dict.pop(item)

    return score_dict

def abnormal_pattern_ranker_custom(normal_pattern_dict, abnormal_pattern_dict, min_diff=2):
    score_dict = {}
    for key in abnormal_pattern_dict.keys():
        if key in normal_pattern_dict.keys():
            diff_value = normal_pattern_dict[key] - abnormal_pattern_dict[key]
            if abs(diff_value) >= min_diff:
                score_dict[key] = diff_value
        elif abnormal_pattern_dict[key] >= min_diff:
            score_dict[key] = abnormal_pattern_dict[key]

    return score_dict

global_abnormal_patterns = {}


def pattern_ranker(normal_pattern_dict, normal_event_graphs, abnormal_time, log_template_miner,topk=10, min_score=0.67):
    rca_path = Config.fault_suffering_data_path
    abnormal_pattern_dict, _, alarm_list = get_pattern(abnormal_time, rca_path,log_template_miner)
    abnormal_pattern_score = get_pattern_ranked_dict(
        normal_pattern_dict, abnormal_pattern_dict, min_score)
    score_dict = {}
    for key in normal_pattern_dict.keys():
        if normal_pattern_dict[key] > 5:
            if key not in score_dict.keys():
                score_dict[key] = 0
            if key in abnormal_pattern_dict.keys():
                score_dict[key] = 1.0 * normal_pattern_dict[key] / \
                    (abnormal_pattern_dict[key] + normal_pattern_dict[key])
                if score_dict[key] < 0.5:
                    score_dict[key] = 1.0 - score_dict[key]
                # print(abnormal_pattern_dict[key],
                #       normal_pattern_dict[key], score_dict[key])
            else:
                score_dict[key] = 1.0
                # print(normal_pattern_dict[key], score_dict[key])

    move_list = set()
    for key, value in score_dict.items():
        # only consider score > 0.66, i.e., 1 / 1 + 0.5
        if float(value) < min_score:
            # logger.info("move key %s because score %s < 0.66" % (key, value))
            move_list.add(key)
    for item in move_list:
        score_dict.pop(item)

    # logger.info("Old Score List: %s" % score_dict)

    move_list = set()
    for key in score_dict.keys():
        # logger.info("%s %s %s %s" % (key, from_id_to_template(int(key.split("_")[0])), from_id_to_template(
        #     int(key.split("_")[1])), value))
        # only consider the root of child graph
        log_var = from_id_to_template(int(key.split("_")[1]),log_template_miner)
        if "Cpu" not in log_var and "Network" not in log_var and "Memory" not in log_var:
            for key1 in score_dict.keys():
                if int(key.split("_")[0]) == int(key1.split("_")[1]) and score_dict[key] <= score_dict[key1]:
                    # logger.info("move key %s because it has root key %s" %
                    #             (key, key1))
                    move_list.add(key)
    for item in move_list:
        score_dict.pop(item)

    result_list = []
    deepth_dict = {}
    for key, value in score_dict.items():
        deepth, pod = get_event_depth_pod(normal_event_graphs, key)
        if pod not in deepth_dict:
            deepth_dict[pod] = deepth
        elif deepth_dict[pod] < deepth:
            deepth_dict[pod] = deepth

        if pod == "":
            pod = "frontend-579b9bff58-t2dbm"
            deepth = 1
        alarm_flag = False
        if len(alarm_list) > 0:
            for i in range(len(alarm_list)):
                item = alarm_list[i]
                if item["pod"] == pod:
                    result_list.append({"events": key, "score": value,
                                        "deepth": deepth, "pod": pod, "resource": item["alarm"][0]["metric_type"]})
                    alarm_flag = True
                    break
        if alarm_flag == False:
            result_list.append({"events": key, "score": value,
                                "deepth": deepth, "pod": pod})

    # if many alarm in one service instane, only persistent the deepest one
    move_list = set()
    for item in alarm_list:
        if item["pod"] in deepth_dict.keys():
            max_deep = deepth_dict[item["pod"]]
            mv_flag = False
            for i in range(len(result_list)):
                item1 = result_list[i]
                if "resource" in item1.keys():
                    if item1["pod"] == item["pod"] and item1["resource"] == item["alarm"][0]["metric_type"]:
                        if max_deep > item1["deepth"]:
                            move_list.add(i)
                        elif max_deep == item1["deepth"] and mv_flag == True:
                            move_list.add(i)
                        else:
                            mv_flag = True

    move_list = list(move_list)
    move_list.reverse()
    try:
        for item in move_list:
            result_list.pop(item)
    except Exception as e:
        pass
        logger.error("Catch an exception: %s", e)
        pass

    # if score is the same, deeper is prefer
    result_list = sorted(result_list, key=lambda i: (
        i['score'], i['deepth']), reverse=True)

    logger.info("Soted Result List: %s" % result_list)

    # for key, value in range(len(score_dict)):
    #     logger.info("%s %s %s %s %s" % (key, from_id_to_template(int(key.split("_")[0])), from_id_to_template(
    #         int(key.split("_")[1])), value["score"], value["deepth"]))
    return result_list, abnormal_pattern_score

def pattern_ranker_custom(fault_free_pattern, fault_suffering_event_graphs, fault_suffering_pattern, log_template_miner, topk=10, min_diff=1):
    abnormal_pattern_score = abnormal_pattern_ranker_custom(
        fault_free_pattern, fault_suffering_pattern, min_diff)
    error_eventids = [185, 187, 188, 189, 201, 204, 205, 207, 208, 209]
    
    patterns_noerror =  {
        k: v for k, v in abnormal_pattern_score.items() 
        if not any(str(id_) in k.split('_') for id_ in error_eventids)
    }
    
    patterns_error =  {
        k: v for k, v in abnormal_pattern_score.items() 
        if any(str(id_) in k.split('_') for id_ in error_eventids)
    }

    reuslts_noerror = pattern_ranker_fromscore(patterns_noerror, fault_suffering_event_graphs, log_template_miner, topk)
    reuslts_error = pattern_ranker_fromscore(patterns_error, fault_suffering_event_graphs, log_template_miner, topk)
    
    return reuslts_noerror[0:topk], reuslts_error

def pattern_ranker_fromscore(abnormal_pattern_score, fault_suffering_event_graphs, log_template_miner, topk=10):
    move_list = set()
    for key in abnormal_pattern_score.keys():
        # only consider the root of child graph
        log_var = from_id_to_template(int(key.split("_")[1]),log_template_miner)
        if "Cpu" not in log_var and "Network" not in log_var and "Memory" not in log_var:
            for key1 in abnormal_pattern_score.keys():
                if int(key.split("_")[0]) == int(key1.split("_")[1]) and abs(abnormal_pattern_score[key]) <= abs(abnormal_pattern_score[key1]):
                    move_list.add(key)
    for item in move_list:
        abnormal_pattern_score.pop(item)

    result_list = []
    deepth_dict = {}
    for key, value in abnormal_pattern_score.items():
        deepth, pod = get_event_depth_pod(fault_suffering_event_graphs, key)
        
        if pod not in deepth_dict:
            deepth_dict[pod] = {}
        if key not in deepth_dict[pod]:
            deepth_dict[pod][key] = deepth
        elif deepth_dict[pod][key] < deepth:
            deepth_dict[pod][key] = deepth

        if pod == "":
            deepth = 1
            pod = "frontend-579b9bff58-t2dbm"

        result_list.append({"events": key, "score": value,
                                "deepth": deepth, "pod": pod})

    # if many alarm in one service instane, only persistent the deepest one
    move_list = set()
    alarm_eventids=['184', '92']
    for key_pod in deepth_dict.keys():
        pod_events = deepth_dict[key_pod]
            # Filter keys that contain any of the target ids
        matching_keys = {k: v for k, v in pod_events.items() 
                    if any(id in k for id in alarm_eventids)}
    
        # If no matches found, return None
        if not matching_keys:
            continue

        # Return the key with maximum depth value
        deepest_key = max(matching_keys.items(), key=lambda x: x[1])[0]
            # Create move list with all matching keys except the deepest
        for key in matching_keys.keys():
            if matching_keys[key] < matching_keys[deepest_key]:
                move_list.add(key)

    result_list = [d for d in result_list if d['events'] not in move_list]

    # if score is the same, deeper is prefer
    result_list = sorted(result_list, key=lambda i: (
        abs(i['score']), i['deepth']), reverse=True)
    
    return result_list[0:topk]


def evaluation(normal_time_list, fault_inject_path,log_template_miner):
    """
    func evaluation: evaluate nezha's precision in inner-service level
    para:
    - normal_time_list:  list of normal construction time
    - fault_inject_list: list of ground truth
    return:
    nezha's precision
    """
    fault_number = 0
    top_list = []
    fault_free_data_path = Config.fault_free_data_path


    normal_time = normal_time_list[0]
       
    normal_pattern_list, normal_event_graphs, normal_alarm_list = get_pattern(
        normal_time, fault_free_data_path,log_template_miner)
    f = open(fault_inject_path)
    fault_inject_data = json.load(f)
    f.close()

    root_cause_file = fault_free_data_path + "/root_cause.json"

    root_cause_lit_file = open(root_cause_file)
    root_cause_list = json.load(root_cause_lit_file)
    root_cause_lit_file.close()
    
    

    for i in range(len(fault_inject_data)):
        fault_number = fault_number + 1
        
        fault = fault_inject_data[i]
        inject_time = ':'.join(fault['inject_time'].split(':')[:-1])
        inject_time_dt = datetime.strptime(inject_time, "%Y-%m-%d %H:%M")
        if fault['inject_time_next']:
            inject_time_next = ':'.join(fault['inject_time_next'].split(':')[:-1])
            inject_time_next_dt = datetime.strptime(inject_time_next, "%Y-%m-%d %H:%M")
        else:
            inject_time_next_dt = inject_time_dt + timedelta(minutes=3)
        
        # Generate all datetimes in minute steps between start and end
        faulty_dts = []
        current_datetime = inject_time_dt
        current_datetime += timedelta(minutes=1)
        while current_datetime < inject_time_next_dt and len(faulty_dts) < 2:
            faulty_dts.append(current_datetime.strftime("%Y-%m-%d %H:%M"))
            current_datetime += timedelta(minutes=1)
            
        inject_service = fault["inject_pod"].rsplit('-', 1)[0]
        inject_service = inject_service.rsplit('-', 1)[0]
        
        abnormal_time = faulty_dts[0]
        
        result_list, abnormal_pattern_score = pattern_ranker(
            normal_pattern_list, normal_event_graphs, abnormal_time,log_template_miner)

        logger.info("%s Inject RCA Result:", fault["inject_time"])
        logger.info("%s Inject Ground Truth: %s, %s",
                    fault["inject_time"], fault["inject_pod"], fault["inject_type"])
        topk = 1

        root_cause = root_cause_list[inject_service][fault["inject_type"]].split(
            "_")

        if len(root_cause) == 1:
            for i in range(len(result_list)):
                if "resource" in result_list[i].keys():
                    if str(root_cause[0]) in str(result_list[i]["resource"]) and str(fault["inject_pod"]) in str(result_list[i]["pod"]):
                        top_list.append(topk)
                        logger.info("%s Inject Ground Truth: %s, %s score %s", fault["inject_time"],
                                    fault["inject_pod"], fault["inject_type"], topk)
                        break
                else:
                    if i > 0:
                        if result_list[i-1]["score"] == result_list[i]["score"] and result_list[i-1]["deepth"] == result_list[i]["deepth"]:
                            continue
                        else:
                            topk = topk + 1
                    elif i == 0:
                        topk = topk + 1
        elif len(root_cause) == 2:
            for i in range(len(result_list)):
                if root_cause[0] in from_id_to_template(int(result_list[i]["events"].split(
                        "_")[0]),log_template_miner) and root_cause[1] in from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner) and str(fault["inject_pod"]) in str(result_list[i]["pod"]):
                    top_list.append(topk)
                    logger.info("%s Inject Ground Truth: %s, %s score %s", fault["inject_time"],
                                fault["inject_pod"], fault["inject_type"], topk)
                    break
                else:
                    if i > 0:
                        # logger.info("%s, %s",
                        #             result_list[i-1]["score"], result_list[i]["score"])
                        if result_list[i-1]["score"] == result_list[i]["score"] and result_list[i-1]["deepth"] == result_list[i]["deepth"]:
                            continue
                        else:
                            topk = topk + 1
                    elif i == 0:
                        topk = topk + 1
        else:
            logger.info("%s", root_cause)
        
        result_len = len(result_list)
        if result_len > 10:
            result_len = 10

        for i in range(result_len):
            if "resource" in result_list[i].keys():
                logger.info("source :%s, target: %s, score: %s, deepth: %s, pod %s, resource alert %s" % (
                    from_id_to_template(int(result_list[i]["events"].split("_")[0]),log_template_miner), from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner), result_list[i]["score"], result_list[i]["deepth"], result_list[i]["pod"], result_list[i]["resource"]))
            else:
                logger.info("source :%s, target: %s, score: %s, deepth: %s, pod %s" % (from_id_to_template(int(result_list[i]["events"].split("_")[
                            0]), log_template_miner), from_id_to_template(int(result_list[i]["events"].split("_")[1]), log_template_miner), result_list[i]["score"], result_list[i]["deepth"], result_list[i]["pod"]))

                for item in abnormal_pattern_score:
                    if result_list[i]["events"].split("_")[0] == item.split("_")[0]:
                        logger.info("actual pattern source :%s, target: %s" % (from_id_to_template(int(item.split("_")[
                                    0]),log_template_miner), from_id_to_template(int(item.split("_")[1]),log_template_miner)))
                        break

        logger.info("")


    logger.info("%s", top_list)
    top5 = 0
    top1 = 0
    top3 = 0
    all_num = 0
    for num in top_list:
        if num <= 5:
            top5 += 1
        if num <= 3:
            top3 += 1
        if num == 1:
            top1 += 1
        all_num += num

    logger.info('-------- %s Fault numbuer : %s-------',fault_number)
    logger.info('--------AIS@1 Result-------')
    logger.info("%f %%" % (top1/fault_number * 100))
    logger.info('--------AIS@3 Result-------')
    logger.info("%f %%" % (top3/fault_number * 100))
    logger.info('--------AIS@5 Result-------')
    logger.info("%f %%" % (top5/fault_number * 100))
    # logger.info('--------MAR Result-------')
    # logger.info("%f" % (all_num/fault_number))


def evaluation_min_score(normal_time_list, fault_inject_list,log_template_miner):
    """
    func evaluation: evaluate nezha's precision in inner-service level when assign different  min_score
    para:
    - normal_time_list:  list of normal construction time
    - fault_inject_list: list of ground truth
    return:
    nezha's precision
    """
    fault_number = 0
    top_list = []
    min_score_list = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    construction_data_path = dirname(__file__) +  "/construct_data"

    for min_score in min_score_list:
        for i in range(len(fault_inject_list)):
            ground_truth_path = fault_inject_list[i]
            normal_time = normal_time_list[i]

            normal_pattern_list, normal_event_graphs, normal_alarm_list = get_pattern(
                normal_time, construction_data_path,log_template_miner)
            f = open(ground_truth_path)
            fault_inject_data = json.load(f)
            f.close()

            root_cause_file = construction_data_path + "/root_cause.json"

            root_cause_lit_file = open(root_cause_file)
            root_cause_list = json.load()
            root_cause_lit_file.close()

            for hour in fault_inject_data:
                for fault in fault_inject_data[hour]:
                    fault_number = fault_number + 1

                    min = int(fault["inject_time"].split(":")[1]) + 2

                    if min >= 60:
                        hour_min = fault["inject_time"].split(" ")[1]
                        hour = int(hour_min.split(":")[0])
                        if hour < 9:
                            abnormal_time = fault["inject_time"].split(
                                " ")[0] + " 0" + str(hour+1) + ":0" + str(min-60)
                        else:
                            abnormal_time = fault["inject_time"].split(
                                " ")[0] + " " + str(hour+1) + ":0" + str(min-60)
                    elif min < 10:
                        abnormal_time = fault["inject_time"].split(
                            ":")[0] + ":0" + str(min)
                    else:
                        abnormal_time = fault["inject_time"].split(
                            ":")[0] + ":" + str(min)
                    # logger.info("%s Inject Ground Truth: %s, %s, %s", fault["inject_time"],
                    #             fault["inject_pod"], fault["inject_type"], fault["root_cause"])
                    result_list, abnormal_pattern_score = pattern_ranker(
                        normal_pattern_list, normal_event_graphs, abnormal_time, min_score=min_score, log_template_miner=log_template_miner)

                    # root_cause = fault["root_cause"].split("_")
                    logger.info("%s Inject RCA Result:", fault["inject_time"])
                    logger.info("%s Inject Ground Truth: %s, %s",
                                fault["inject_time"], fault["inject_pod"], fault["inject_type"])
                    topk = 1

                    inject_service = fault["inject_pod"].rsplit('-', 1)[0]
                    inject_service = inject_service.rsplit('-', 1)[0]
                    root_cause = root_cause_list[inject_service][fault["inject_type"]].split(
                        "_")
                    if len(root_cause) == 1:
                        for i in range(len(result_list)):
                            if "resource" in result_list[i].keys():
                                if str(root_cause[0]) in str(result_list[i]["resource"]) and str(fault["inject_pod"]) in str(result_list[i]["pod"]):
                                    top_list.append(topk)
                                    logger.info("%s Inject Ground Truth: %s, %s score %s", fault["inject_time"],
                                                fault["inject_pod"], fault["inject_type"], topk)
                                    break
                            else:
                                if i > 0:
                                    if result_list[i-1]["score"] == result_list[i]["score"] and result_list[i-1]["deepth"] == result_list[i]["deepth"]:
                                        continue
                                    else:
                                        topk = topk + 1
                                elif i == 0:
                                    topk = topk + 1
                    elif len(root_cause) == 2:
                        for i in range(len(result_list)):
                            if root_cause[0] in from_id_to_template(int(result_list[i]["events"].split(
                                    "_")[0]), log_template_miner) and root_cause[1] in from_id_to_template(int(result_list[i]["events"].split("_")[1]), log_template_miner) and str(fault["inject_pod"]) in str(result_list[i]["pod"]):
                                top_list.append(topk)
                                logger.info("%s Inject Ground Truth: %s, %s score %s", fault["inject_time"],
                                            fault["inject_pod"], fault["inject_type"], topk)
                                break
                            else:
                                if i > 0:
                                    # logger.info("%s, %s",
                                    #             result_list[i-1]["score"], result_list[i]["score"])
                                    if result_list[i-1]["score"] == result_list[i]["score"] and result_list[i-1]["deepth"] == result_list[i]["deepth"]:
                                        continue
                                    else:
                                        topk = topk + 1
                                elif i == 0:
                                    topk = topk + 1
                    else:
                        logger.info("%s", root_cause)

                    for i in range(len(result_list)):
                        if "resource" in result_list[i].keys():
                            logger.info("source :%s, target: %s, score: %s, deepth: %s, pod %s, resource %s" % (
                                from_id_to_template(int(result_list[i]["events"].split("_")[0]),log_template_miner), from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner), result_list[i]["score"], result_list[i]["deepth"], result_list[i]["pod"], result_list[i]["resource"]))
                        else:
                            logger.info("source :%s, target: %s, score: %s, deepth: %s, pod %s" % (from_id_to_template(int(result_list[i]["events"].split("_")[
                                        0]),log_template_miner), from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner), result_list[i]["score"], result_list[i]["deepth"], result_list[i]["pod"]))

                    logger.info("")
        logger.info("%s", top_list)
        top5 = 0
        top1 = 0
        top3 = 0
        all_num = 0
        for num in top_list:
            if num <= 5:
                top5 += 1
            if num <= 3:
                top3 += 1
            if num == 1:
                top1 += 1
            all_num += num

        logger.info("Min Score %f result" % (min_score))
        logger.info('-------- %s Fault numbuer : %s-------',fault_number)
        logger.info('--------R@1 Result-------')
        logger.info("%f %%" % (top1/fault_number * 100))
        logger.info('--------R@3 Result-------')
        logger.info("%f %%" % (top3/fault_number * 100))
        logger.info('--------R@5 Result-------')
        logger.info("%f %%" % (top5/fault_number * 100))
        logger.info('--------MAR Result-------')
        logger.info("%f" % (all_num/fault_number))


def evaluation_pod(normal_time_list, fault_inject_list, log_template_miner):
    """
    func evaluation: evaluate nezha's precision in pod-service level
    para:
    - normal_time_list:  list of normal construction time
    - fault_inject_list: list of ground truth
    return:
    nezha's precision 
    """
    fault_number = 0
    top_list = []
    construction_data_path = dirname(__file__) +  "/construct_data"

    for i in range(len(fault_inject_list)):
        ground_truth_path = fault_inject_list[i]
        normal_time = normal_time_list[i]

        normal_pattern_list, normal_event_graphs, normal_alarm_list = get_pattern(
            normal_time, construction_data_path,log_template_miner)
        f = open(ground_truth_path)
        fault_inject_data = json.load(f)
        f.close()

        root_cause_file = construction_data_path + "/root_cause.json"
        
        root_cause_lit_file = open(root_cause_file)
        root_cause_list = json.load(root_cause_lit_file)
        root_cause_lit_file.close()

        for hour in fault_inject_data:
            for fault in fault_inject_data[hour]:
                fault_number = fault_number + 1

                min = int(fault["inject_time"].split(":")[1]) + 2

                if min >= 60:
                    hour_min = fault["inject_time"].split(" ")[1]
                    hour = int(hour_min.split(":")[0])
                    if hour < 9:
                        abnormal_time = fault["inject_time"].split(
                            " ")[0] + " 0" + str(hour+1) + ":0" + str(min-60)
                    else:
                        abnormal_time = fault["inject_time"].split(
                            " ")[0] + " " + str(hour+1) + ":0" + str(min-60)
                elif min < 10:
                    abnormal_time = fault["inject_time"].split(
                        ":")[0] + ":0" + str(min)
                else:
                    abnormal_time = fault["inject_time"].split(
                        ":")[0] + ":" + str(min)
                # logger.info("%s Inject Ground Truth: %s, %s, %s", fault["inject_time"],
                #             fault["inject_pod"], fault["inject_type"], fault["root_cause"])
                result_list, abnormal_pattern_score = pattern_ranker(
                    normal_pattern_list, normal_event_graphs, abnormal_time, log_template_miner)

                # root_cause = fault["root_cause"].split("_")
                logger.info("%s Inject RCA Pod Result:", fault["inject_time"])
                logger.info("%s Inject Ground Truth: %s, %s",
                            fault["inject_time"], fault["inject_pod"], fault["inject_type"])
                topk = 1

                inject_service = fault["inject_pod"].rsplit('-', 1)[0]
                inject_service = inject_service.rsplit('-', 1)[0]
                root_cause = root_cause_list[inject_service][fault["inject_type"]].split(
                    "_")
                if len(root_cause) == 1:
                    for i in range(len(result_list)):
                        if "resource" in result_list[i].keys():
                            if str(root_cause[0]) in str(result_list[i]["resource"]) and str(fault["inject_pod"]) in str(result_list[i]["pod"]):
                                top_list.append(topk)
                                logger.info("%s Inject Ground Truth: %s, %s score %s", fault["inject_time"],
                                            fault["inject_pod"], fault["inject_type"], topk)
                                break
                        else:
                            if i > 0:
                                if result_list[i-1]["score"] == result_list[i]["score"] and result_list[i-1]["deepth"] == result_list[i]["deepth"]:
                                    continue
                                else:
                                    topk = topk + 1
                            elif i == 0:
                                topk = topk + 1
                elif len(root_cause) == 2:
                    for i in range(len(result_list)):
                        if root_cause[0] in from_id_to_template(int(result_list[i]["events"].split(
                                "_")[0]), log_template_miner) and root_cause[1] in from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner) and str(fault["inject_pod"]) in str(result_list[i]["pod"]):
                            top_list.append(topk)
                            logger.info("%s Inject Ground Truth: %s, %s score %s", fault["inject_time"],
                                        fault["inject_pod"], fault["inject_type"], topk)
                            break
                        else:
                            if i > 0:
                                # logger.info("%s, %s",
                                #             result_list[i-1]["score"], result_list[i]["score"])
                                if result_list[i-1]["score"] == result_list[i]["score"] and result_list[i-1]["deepth"] == result_list[i]["deepth"]:
                                    continue
                                else:
                                    topk = topk + 1
                            elif i == 0:
                                topk = topk + 1
                else:
                    logger.info("%s", root_cause)

                result_len = len(result_list)
                if result_len > 10:
                    result_len = 10

                for i in range(result_len):
                    if "resource" in result_list[i].keys():
                        logger.info("source :%s, target: %s, score: %s, deepth: %s, pod %s, resource %s" % (
                            from_id_to_template(int(result_list[i]["events"].split("_")[0]), log_template_miner), from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner), result_list[i]["score"], result_list[i]["deepth"], result_list[i]["pod"], result_list[i]["resource"]))
                    else:
                        logger.info("source :%s, target: %s, score: %s, deepth: %s, pod %s" % (from_id_to_template(int(result_list[i]["events"].split("_")[
                                    0]),log_template_miner), from_id_to_template(int(result_list[i]["events"].split("_")[1]),log_template_miner), result_list[i]["score"], result_list[i]["deepth"], result_list[i]["pod"]))
                logger.info("")
    logger.info("%s", top_list)
    top5 = 0
    top1 = 0
    top3 = 0
    all_num = 0
    for num in top_list:
        if num <= 5:
            top5 += 1
        if num <= 3:
            top3 += 1
        if num == 1:
            top1 += 1
        all_num += num
    logger.info('-------- %s Fault numbuer : %s-------',fault_number)
    logger.info('--------AS@1 Result-------')
    logger.info("%f %%" % (top1/fault_number * 100))
    logger.info('--------AS@3 Result-------')
    logger.info("%f %%" % (top3/fault_number * 100))
    logger.info('--------AS@5 Result-------')
    logger.info("%f %%" % (top5/fault_number * 100))
    # logger.info('--------MAR Result-------')
    # logger.info("%f" % (all_num/fault_number))


def evaluation_time(ns="hipster"):
    # normal_time = "2022-08-22 03:51"
    # abnormal_time = "2022-08-22 03:52"
    normal_time = "2023-01-29 08:50"
    abnormal_time = "2023-01-29 08:52"

    normal_pattern_list, normal_event_graphs, normal_alarm_list = get_pattern(
        normal_time, construction_data_path)
    start_time = time.time()
    result_list, abnormal_pattern_score = pattern_ranker(
        normal_pattern_list, normal_event_graphs, abnormal_time)
    print(time.time()-start_time)


if __name__ == '__main__':
    normal_time1 = "2022-08-22 03:51"
    path1 = "/root/jupyter/nezha/construction_data/2022-08-22/2022-08-22-fault_list.json"

    normal_time2 = "2022-08-23 17:00"
    path2 = "./construction_data/2022-08-23/2022-08-23-fault_list.json"

    ns = "hipster"
    template_indir = dirname(__file__) + '/log_template'
    config = TemplateMinerConfig()

    config.load(dirname(__file__) + "/log_template/drain3_" + ns + ".ini")
    config.profiling_enabled = False

    path = dirname(__file__) + '/log_template/' + ns + ".bin"
    persistence = FilePersistence(path)
    template_miner = TemplateMiner(persistence, config=config)

    # inject_list = [path1, path2]
    # normal_time_list = [normal_time1, normal_time2]
    # evaluation(normal_time_list, inject_list, ns)

    # normal_time1 = "2023-01-29 08:50"
    # path1 = "/root/jupyter/nezha/construction_data/2023-01-29/2023-01-29-fault_list.json"

    # normal_time2 = "2023-01-30 11:39"
    # path2 = "/root/jupyter/nezha/construction_data/2023-01-30/2023-01-30-fault_list.json"

    # ns = "ts"

    # inject_list = [path1, path2]
    # normal_time_list = [normal_time1, normal_time2]

    inject_path = [path2]
    normal_time_list = [normal_time2]
    evaluation(normal_time_list, inject_path,template_miner)
    # evaluation_pod(normal_time_list, inject_list, ns)
    # evaluation_min_score(normal_time_list, inject_list, ns)

    # evaluation_time()
