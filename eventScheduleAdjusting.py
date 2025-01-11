import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from datetime import datetime, timedelta

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
slack_client = WebClient(token=SLACK_BOT_TOKEN)

def date_to_weekdays(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    weekdays = []
    current_date = start
    while current_date <= end:
        weekday = current_date.strftime("%A")
        if weekday not in ["Saturday", "Sunday"]:
            weekdays.append(weekday)
        current_date += timedelta(days=1)
    return weekdays

def time_to_minutes(time_str):
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes

def is_time_overlapping(time_slot, duration, start_time, end_time):
    slot_start = time_to_minutes(time_slot)
    slot_end = slot_start + int(duration * 60)
    start = time_to_minutes(start_time)
    end = time_to_minutes(end_time)
    return not (slot_end <= start or slot_start >= end)

def find_best_time_slot(users_schedule, mandatory_person, duration, weekdays):
    time_slots = [f"{hour:02d}:{minute:02d}" for hour in range(8, 24) for minute in range(0, 60, 30)]
    best_time_slot = None
    max_participants = 0
    best_unavailable_people = []
    for day in weekdays:
        for time_slot in time_slots:
            participants = 0
            unavailable = []
            for person, schedule in users_schedule.items():
                if person in mandatory_person:
                    available = True
                    for wday, start_time, end_time in schedule:
                        if wday == day and is_time_overlapping(time_slot, duration, start_time, end_time):
                            available = False
                            unavailable.append(person)
                            break
                    if available:
                        participants += 1
                else:
                    available = True
                    for wday, start_time, end_time in schedule:
                        if wday == day and is_time_overlapping(time_slot, duration, start_time, end_time):
                            available = False
                            break
                    if available:
                        participants += 1
            if participants > max_participants:
                max_participants = participants
                best_time_slot = (day, time_slot)
                best_unavailable_people = unavailable
    return best_time_slot, max_participants, best_unavailable_people    


def lambda_handler(event, context):
    # 불가능한 시간 조정

    ## 알고리즘으로 시간표 다시 계산

    data = '''
    [
        {
            "name": "서지은",
            "createdAt": "2025-01-11",
            "schedule": "{ \\"Monday\\": [ { \\"start_time\\": \\"08:00\\", \\"end_time\\": \\"12:30\\", \\"name\\": \\"사회물리학: 네트워크적 접근\\", \\"index\\": 1 }, { \\"start_time\\": \\"14:30\\", \\"end_time\\": \\"15:30\\", \\"name\\": \\"AI 원리 및 최신기술\\", \\"index\\": 2 } ], \\"Tuesday\\": [ { \\"start_time\\": \\"09:00\\", \\"end_time\\": \\"10:00\\", \\"name\\": \\"기계학습\\", \\"index\\": 3 } ], \\"Wednesday\\": [ { \\"start_time\\": \\"13:00\\", \\"end_time\\": \\"15:00\\", \\"name\\": \\"심리학\\", \\"index\\": 4 } ] }"
        },
        {
            "name": "서은원",
            "createdAt": "2025-01-11",
            "schedule": "{ \\"Monday\\": [ { \\"start_time\\": \\"11:00\\", \\"end_time\\": \\"12:30\\", \\"name\\": \\"사회물리학: 네트워크적 접근\\", \\"index\\": 1 }, { \\"start_time\\": \\"14:30\\", \\"end_time\\": \\"15:30\\", \\"name\\": \\"AI 원리 및 최신기술\\", \\"index\\": 2 } ], \\"Tuesday\\": [ { \\"start_time\\": \\"09:00\\", \\"end_time\\": \\"10:00\\", \\"name\\": \\"기계학습\\", \\"index\\": 3 } ], \\"Wednesday\\": [ { \\"start_time\\": \\"13:00\\", \\"end_time\\": \\"15:00\\", \\"name\\": \\"심리학\\", \\"index\\": 4 } ] }"
        }
    ]
    '''

    parsed_data = json.loads(data)
    users_schedule = {}

    start_date = "2025-01-11"
    end_date = "2025-01-13"
    mandatory_person = ["서은원"]
    duration = 0.5  # 30분


    for user in parsed_data:
        name = user["name"]
        schedule_data = json.loads(user["schedule"])
        times = []
        for day, day_schedule in schedule_data.items():
            for item in day_schedule:
                start_time = item["start_time"]
                end_time = item["end_time"]
                times.append((day, start_time, end_time))
        users_schedule[name] = times

    weekdays = date_to_weekdays(start_date, end_date)

    print(find_best_time_slot(users_schedule, mandatory_person, duration, weekdays))

    """
    특정 슬랙 스레드의 메시지를 가져오는 함수
    :param channel_id: 메시지가 속한 채널 ID
    :param thread_ts: 스레드의 시작 메시지 타임스탬프
    :return: 스레드 메시지 목록
    """
    # try:
    #     # conversations.replies API 호출
    #     response = client.conversations_replies(channel=channel_id, ts=thread_ts)

    #     # 메시지 목록 반환
    #     messages = response.get("messages", [])
    #     return messages
    # except SlackApiError as e:
    #     print(f"Error fetching thread messages: {e.response['error']}")
    #     return []

    # return {
    #     'statusCode': 200,
    #     'body': json.dumps('good')
    # }

