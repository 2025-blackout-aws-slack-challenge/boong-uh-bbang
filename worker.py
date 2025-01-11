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

def get_claude_timetable_response(prompt, image_data, mimetype):
    timetable_structure = {
        "Monday": [
            {
                "start_time": "The start time of the class. (e.g. 09:00)",
                "end_time": "The end time of the class. (e.g. 10:00)",
                "name": "The name of the class. (e.g. Introduction to Computer Science)",
                "index": "The index of the class. (e.g. 1)"
            }
        ],
        "Tuesday": [],
        "Wednesday": [],
        "Thursday": [],
        "Friday": []
    }

    timetable_example = {
      "Monday": [
        {
          "start_time": "11:00",
          "end_time": "12:00",
          "name": "사회물리학: 네트워크적 접근",
          "index": 1
        },
        {
          "start_time": "13:00",
          "end_time": "15:00",
          "name": "AI 원리 및 최신기술",
          "index": 2
        },
      ],
      "Tuesday": [
        {
          "start_time": "09:00",
          "end_time": "12:00",
          "name": "확장현실 프로젝트",
          "index": 1
        }
      ],
      "Wednesday": [],
      "Thursday": [
        {
          "start_time": "11:00",
          "end_time": "12:00",
          "name": "사회물리학: 네트워크적 접근",
          "index": 1
        },
        {
          "start_time": "13:00",
          "end_time": "14:00",
          "name": "다변수해석학과 응용",
          "index": 2
        },
        {
          "start_time": "16:00",
          "end_time": "17:00",
          "name": "프로그래밍 언어 및 컴파일러",
          "index": 3
        }
      ],
      "Friday": []
    }

    system_prompt = f'''You are a time table manager for a school club. Users will give you their timetables in various formats, not limited to text and images. Analyze the message and extract the timetable information. Respond with the extracted information in the following structured format:

    # Format
    {json.dumps(timetable_structure)}

    # Example
    {json.dumps(timetable_example)}

    # Note
    - If the given information is not enough to extract the timetable. Do not ask for additional information.
    '''


    prompt = prompt if prompt else "empty"

    try:
        content = []

        if image_data:
            content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mimetype,
                                "data": image_data
                            }
                        })
        
        content.append({
            "type": "text",
            "text": prompt
        })

        # Bedrock 요청 바디 구성
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "temperature": 0.7
        })
        
        # Bedrock API 호출
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            contentType='application/json',
            body=body
        )
        
        # 응답 파싱
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        logger.error(f"Bedrock API 에러: {str(e)}")
        return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."

def get_claude_meeting_response(prompt):

    today = datetime.now().strftime('%Y-%m-%d')
    whatday = datetime.now().strftime('%A')

    example_output = {
        "meeting_duration": "1 hour",
        "meeting_date_range": "2023-05-31 to 2023-06-01",
        "participants": ["U01ABCDEF", "U01GHIJKLM"],
        "meeting_schedule_finalization_deadline": "2023-05-31"
    }

    meeting_structure = {
        "meeting_duration": "The duration of the meeting in hours or minutes. (e.g. 1 hour, 30 minutes)",
        "meeting_date_range": "The range of dates for the meeting. (e.g. 2023-05-31 to 2023-06-01)",
        "participants": "The list of participants for the meeting. This will be given as slack user IDs. (e.g. U01ABCDEF, U01GHIJKLM)",
        "meeting_schedule_finalization_deadline": "The deadline for finalizing the meeting schedule. This will be given as a date. (e.g. 2023-05-31)",
        "request": "회의 정보를 추출하기 위해 필요한 추가 정보를 요청하세요."
    }

    system_prompt = f'''You are a meeting scheduler for a school club. Users will request you to extract the meeting information from the message. Analyze the message and extract the following information: meeting duration, meeting date range, participants, and meeting schedule finalization deadline. 

Meeting duration: The duration of the meeting in hours or minutes. (e.g. 1 hour, 30 minutes)

Meeting date range: The range of dates for the meeting. (e.g. 2023-05-31 to 2023-06-01) Users may provide absolute dates or relative dates(e.g. tomorrow, next week), and you should convert them to absolute dates. Today's date is {today} {whatday}. The output should be in the format of "YYYY-MM-DD to YYYY-MM-DD".

Participants: The list of participants for the meeting. This will be given as slack user IDs. (e.g. U01ABCDEF, U01GHIJKLM)

Meeting schedule finalization deadline: The deadline for finalizing the meeting schedule. This will be given as a date. (e.g. 2023-05-31) Users may provide absolute dates or relative dates(e.g. tomorrow, next week), and you should convert them to absolute dates. Today's date is {today} {whatday}. The output should be in the format of "YYYY-MM-DD".

Example input: "Can we schedule a meeting for 1 hour during next week with @U01ABCDEF, @U01GHIJKLM? Let's finalize the schedule by tomorrow."

Example output: {json.dumps(example_output)}

Strictly follow the output format

If the given information is not enough to extract the meeting information, ask for the missing information in the 'request' field. If not, leave it empty.
Request should be written in Korean.

# Format
{json.dumps(meeting_structure)}
 '''

    try:
        content = []
        
        content.append({
            "type": "text",
            "text": prompt
        })

        # Bedrock 요청 바디 구성
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "temperature": 0.7
        })
        
        # Bedrock API 호출
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            contentType='application/json',
            body=body
        )
        
        # 응답 파싱
        response_body = json.loads(response['body'].read())
        print("model response:", response_body['content'][0]['text'])

        extracted_info = json.loads(response_body['content'][0]['text'])

        request = extracted_info.get('request', None)
        

        return extracted_info, request
        
    except Exception as e:
        logger.error(f"Bedrock API 에러: {str(e)}")
        return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."

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

            meeting_info, request = get_claude_meeting_response(combined_message)

            if request:
                # Request additional informatio
                slack_client.chat_postMessage(
                    channel=channel_id,
                    text=f'''<@{user_id}>
{request}
''',
                    thread_ts=thread_ts
                )
            else:
                # Send extracted meeting information
                slack_client.chat_postMessage(
                    channel=channel_id,
                    text=f'''<@{user_id}>
모든 정보를 읽었습니다! 아래는 회의 일정입니다:
{json.dumps(meeting_info, indent=2)}

유저 회의 일정을 업데이트했어요! 😊
''',
                    thread_ts=thread_ts
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
            claude_response = get_claude_timetable_response(message, image_base64, fetched_file['mimetype'] if base64 else None)
            
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