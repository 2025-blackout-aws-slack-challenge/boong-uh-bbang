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
import eventScheduleAdjusting

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

    print(body)
    print(event_type)

    try:
        # 이벤트 타입과 서브타입 체크
        event_type = body['event']['type']

        if event_type == 'app_mention':
            thread_messages = fetch_thread_messages(channel_id, body['event']['thread_ts'] if 'thread_ts' in body['event'] else body['event']['ts'])
            combined_message = combine_thread_messages(thread_messages, bot_user_id)
            # 멘션을 제외한 실제 메시지 추출
            print('combined_message:', combined_message)

            meeting_info, request = get_claude_meeting_response(bedrock_runtime, combined_message)

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

                user_schedules = eventScheduleAdjusting.get_user_schedules(participants_id)
                weekdays = eventScheduleAdjusting.date_to_weekdays(start_date, end_date)
                
                best_time_slots, max_participants, unavailable_people = eventScheduleAdjusting.find_best_time_slot(user_schedules, participants_id, duration, weekdays)
                
                response_message = ''

                if best_time_slots:
                    response_message += f"최적의 시간대 (참석 가능한 최대 인원: {max_participants}명):\n"
                    for day, time in best_time_slots:
                        response_message += f"{day} {time}\n"
                    if unavailable_people:
                        response_message += f"불참자 수: {len(unavailable_people)}\n"
                    else:
                        response_message += "불참자가 없습니다.\n"
                else:
                    response_message += "모든 필수 참여자가 참석할 수 있는 시간대가 없습니다.\n"

                for participant in participants_id:
                    response_message += f"<@{participant}>님 "
                
                response_message += "불가능한 시간대가 있나요? 알려주세요!"

                # Send extracted meeting information
                slack_client.chat_postMessage(
                    channel=channel_id,
                    text=response_message
                )

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
            claude_response = get_claude_timetable_response(bedrock_runtime, message, image_base64, fetched_file['mimetype'] if base64 else None)
            
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