import os
import json
import logging
import boto3
from botocore.config import Config
import urllib.request
import base64
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
from getClaudeTimetableResponse import get_claude_timetable_response
from getClaudeMeetingResponse import get_claude_meeting_response
from getClaudeMeetingPreference import get_claude_meeting_preference
import eventScheduleAdjusting
import re

# 로깅 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack & Bedrock 클라이언트 초기화
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
slack_client = WebClient(token=SLACK_BOT_TOKEN)

my_config = Config(
    region_name = 'us-west-2'
)

bedrock_runtime = boto3.client('bedrock-runtime', config=my_config)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table('testDB')

bot_user_id = slack_client.auth_test()['user_id']


def download_image(url, headers=None):
    # 이미지 다운로드
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as response:
        return response.read()

def format_schedule(schedule):
    schedule = json.loads(schedule)

    result = "### 유저 시간표 ###\n\n"
    for day, events in schedule.items():
        result += f"#### {day}\n"
        if events:
            for event in events:
                result += f"- **{event['name']}**: {event['start_time']} ~ {event['end_time']}\n"
        else:
            result += "- 일정 없음\n"
        result += "\n"  # 하루 끝나면 빈 줄 추가
    return result

def fetch_thread_messages(channel_id, thread_ts):
    try:
        response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts)

        return response['messages']
    except SlackApiError as e:
        logger.error(f"Failed to fetch thread messages: {e.response['error']}")
        return []

def combine_thread_messages(messages, bot_user_id):
    """
    Combine all messages in a thread into a single prompt,
    including the sender's information, but exclude the bot's messages.
    """
    combined_message = ""
    for message in messages:
        # Skip messages sent by the bot
        if message.get('user') == bot_user_id or 'bot_id' in message:
            combined_message += f"Bot: {message.get('text', '')}\n"
        
        user_id = message.get('user', 'Unknown')
        text = message.get('text', '')
        combined_message += f"<@{user_id}>: {text}\n"
    return combined_message.strip()

def lambda_handler(event, context):
    # API Gateway에서 전달된 바디 파싱
    body = json.loads(event['body'])
    
    event_type = body['type']
    claude_response = ''
    thread_ts = body['event']['ts']
    channel_id = body['event']['channel']
    user_id = body['event']['user']
    text = body['event']['text']

    parent_user_id = body['event']['parent_user_id'] if 'parent_user_id' in body['event'] else None

    print(body)
    print(event_type)

    print('parent_user_id:', parent_user_id, 'bot_user_id:', bot_user_id)

    try:
        # 이벤트 타입과 서브타입 체크
        event_type = body['event']['type']

        if event_type == 'app_mention':
            thread_messages = fetch_thread_messages(channel_id, body['event']['thread_ts'] if 'thread_ts' in body['event'] else body['event']['ts'])
            combined_message = combine_thread_messages(thread_messages, bot_user_id)
            # 멘션을 제외한 실제 메시지 추출
            print('combined_message:', combined_message)

            if parent_user_id != bot_user_id:
              # 봇을 통해 회의 정보 추출
              meeting_info, request = get_claude_meeting_response(bedrock_runtime, combined_message)
              # remove the bot from participants
              meeting_info['participants'] = [participant for participant in meeting_info['participants'] if participant != bot_user_id]

              if request:
                  # Request additional informatio
                  slack_client.chat_postMessage(
                      channel=channel_id,
                      text=f'''<@{user_id}> {request} ''',
                      thread_ts=thread_ts
                  )
              else:
                  [start_date, end_date] = meeting_info['meeting_date_range'].split(' to ')
                  participants_id = meeting_info['participants']
                  duration = meeting_info['meeting_duration']
                  finalize_deadline = meeting_info['meeting_schedule_finalization_deadline']

                  response_message = ''

                  response_message += f"회의 일정: {start_date} ~ {end_date} \n"
                  response_message += f"회의 참석자: "
                  for participant in participants_id:
                      response_message += f"<@{participant}>님 "

                  response_message += f"\n회의 시간: {duration} 시간 \n"

                  response_message += "다들 회의 괜찮으신가요? 의견을 남겨주세요! 😊"

                  # Send extracted meeting information
                  slack_client.chat_postMessage(
                      channel=channel_id,
                      text=response_message
                  )
            else:
              # 유저 의견을 받고 최종 회의 일정을 잡는다.
              schedule_regex = r"회의 일정:\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})"
              participants_regex = r"<@([A-Z0-9]+)>님"
              duration_regex = r"회의 시간:\s*(\d+)\s*시간"

              schedule_match = re.search(schedule_regex, combined_message)
              duration_match = re.search(duration_regex, combined_message)

              participants = re.findall(participants_regex, combined_message)
              participants_set = set(participants)
              participants = list(participants_set)

              start_date, end_date = schedule_match.groups() if schedule_match else (None, None)
              duration = int(duration_match.group(1)) if duration_match else None

              print('start_date:', start_date, 'end_date:', end_date, 'duration:', duration, 'participants:', participants)

              users_schedule = eventScheduleAdjusting.get_user_schedules(participants)

          
              weekdays = eventScheduleAdjusting.date_to_weekdays(start_date, end_date)



              best_time_slots, max_participants, unavailable_people = eventScheduleAdjusting.find_best_time_slot(users_schedule, participants, duration, weekdays)

              final_meeting_info, is_everyone_has_preference = get_claude_meeting_preference(bedrock_runtime, combined_message, best_time_slots, bot_user_id)

              if is_everyone_has_preference:
                  # Send the final meeting schedule
                  response_message = "회의 일정이 잡혔어요! 아래는 회의 일정이에요. 확인해주세요.\n"
                  response_message += f"회의 일정: {final_meeting_info['best_time']}\n"
                  response_message += "참석자: "
                  for participant in final_meeting_info['participants']:
                      response_message += f"<@{participant['user_id']}>님 "
              
                  slack_client.chat_postMessage(
                      channel=channel_id,
                      text=response_message
                  )
              else:
                  pass

        if event_type == 'message' and body['event']['channel_type'] == 'im' and 'bot_profile' not in body['event']:
            message = text
            image_base64 = ""

            if 'files' in body['event']:
                file_info = body['event']['files'][0]
                print('file_info:', file_info)

                if file_info['filetype'] in ['jpg', 'jpeg', 'png']:
                    fetched_file = slack_client.files_info(file=file_info['id'])['file']

                    print('fetched_file:', fetched_file)

                    # 이미지 다운로드
                    file_url = fetched_file['url_private']
                    headers = {'Authorization': f'Bearer {SLACK_BOT_TOKEN}'}
                    image_data = download_image(file_url, headers)
                    
                    # Bedrock으로 분석
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Bedrock을 통해 Claude 응답 생성
            claude_response = get_claude_timetable_response(bedrock_runtime, message, image_base64, fetched_file['mimetype'] if image_base64 else None)
            
            readable_schedule = format_schedule(claude_response)

            # 슬랙에 메시지 전송
            slack_client.chat_postMessage(
                channel=channel_id,
                text=f'''<@{user_id}>
시간표를 읽어왔어요! 아래는 유저의 시간표에요. 확인해주세요.
{readable_schedule}

유저 시간표를 업데이트했어요! 잘못된 부분이 있다면 말씀해주세요! 😊
'''
            )

            try:
                name = body['event']['user']

                item = {
                    "name": name,
                    "schedule": claude_response,
                    "createdAt": datetime.utcnow().isoformat()
                }
                table.put_item(Item=item)
                print(f"[INFO] DynamoDB 저장 완료: {item}")
            except Exception as e:
                print(f"[ERROR] DynamoDB 저장 중 오류 발생: {e}")
        
    except SlackApiError as e:
        logger.error(f"Slack API 에러: {e.response['error']}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        logger.error(f"에러 발생: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Success'})
    }