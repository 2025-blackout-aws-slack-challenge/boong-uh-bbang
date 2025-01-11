import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from datetime import datetime, timedelta
import boto3
import traceback
from boto3.dynamodb.conditions import Key


SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
slack_client = WebClient(token=SLACK_BOT_TOKEN)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table('testDB')


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

def find_best_time_slot(users_schedule, user_id, duration, weekdays):
    time_slots = [f"{hour:02d}:{minute:02d}" for hour in range(8, 24) for minute in range(0, 60, 30)]
    best_time_slot = None
    max_participants = 0
    best_unavailable_people = []
    for day in weekdays:
        for time_slot in time_slots:
            participants = 0
            unavailable = []
            for person, schedule in users_schedule.items():
                if person in user_id:
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

    participants_id = ['U0792169H4Y', 'U0430P2DSVA', 'UH73HNUFR']

    ## 알고리즘으로 시간표 다시 계산
    data = []

    try:
        for participant_id in participants_id:
            response = table.query(
                KeyConditionExpression = Key('name').eq(participant_id)
            )
            data.extend(response.get('Items', []))
        print(f"DB 불러오기 성공 : {data}")
    except Exception as e:
        print(f"DB 불러오기 실패 : {e}")
        print(traceback.format_exc())


    # parsed_data = json.loads(data)
    users_schedule = {}

    start_date = "2025-01-11"
    end_date = "2025-01-13"
    # user_id = ["서은원"]
    duration = 0.5  # 30분


    for user in data:
        participant_id = user["name"]
        schedule_data = json.loads(user["schedule"])
        times = []
        for day, day_schedule in schedule_data.items():
            for item in day_schedule:
                start_time = item["start_time"]
                end_time = item["end_time"]
                times.append((day, start_time, end_time))
        users_schedule[participant_id] = times

    weekdays = date_to_weekdays(start_date, end_date)

    print(find_best_time_slot(users_schedule, participants_id, duration, weekdays))

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

