import os
import json
import logging
import boto3
from botocore.config import Config
import urllib.request
import base64
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import datetime as datetime

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
    },
    {
      "start_time": "13:00",
      "end_time": "14:00",
      "name": "다변수해석학과 응용",
      "index": 2
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
    },
    {
      "start_time": "16:00",
      "end_time": "17:00",
      "name": "GIST대학 콜로퀴움",
      "index": 4
    },
    {
      "start_time": "18:00",
      "end_time": "20:00",
      "name": "다변수해석학과 응용",
      "index": 5
    }
  ],
  "Friday": []
}

system_prompt = f'''You are a time table manager for a school club. Users will give you their timetables in various formats, not limited to text and images. Analyze the message and extract the timetable information. Respond with the extracted information in the following structured format:

# Format
{json.dumps(timetable_structure)}

# Example
{json.dumps(timetable_example)}
 '''

def get_claude_response(prompt, image_data, mimetype):
    

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

def download_image(url, headers=None):
    # 이미지 다운로드
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as response:
        return response.read()

def lambda_handler(event, context):
    # API Gateway에서 전달된 바디 파싱
    body = json.loads(event['body'])
    
    event_type = body['type']
    claude_response = ''
    
    try:
        # 이벤트 타입과 서브타입 체크
        event_type = body['event']['type']
        
        # app_mention 이벤트 처리
        if event_type == 'app_mention':
            print("app_mention")
            channel_id = body['event']['channel']
            user_id = body['event']['user']
            text = body['event']['text']
            
            # 멘션을 제외한 실제 메시지 추출
            message = text.split('>', 1)[1].strip()

            image_base64 = ""

            if 'files' in body['event']:
                file_info = body['event']['files'][0]
                if file_info['mimetype'].startswith('image/'):
                    # 이미지 다운로드
                    file_url = file_info['url_private']
                    headers = {'Authorization': f'Bearer {SLACK_BOT_TOKEN}'}
                    image_data = download_image(file_url, headers)
                    
                    # Bedrock으로 분석
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Bedrock을 통해 Claude 응답 생성
            claude_response = get_claude_response(message, image_base64, file_info['mimetype'] if image_base64 else None)
            
            # 슬랙에 메시지 전송
            slack_client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}> {claude_response}"
            )
            
        
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
    
    # 디비 저장 로직
    name = body['event']['user']
    
    try:
        item = {
            "name": name,
            "schedule": claude_response,
            "createdAt": datetime.utcnow().isoformat()
        }
        table.put_item(Item=item)
        print(f"[INFO] DynamoDB 저장 완료: {item}")
    except Exception as e:
        print(f"[ERROR] DynamoDB 저장 중 오류 발생: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Success'})
    }