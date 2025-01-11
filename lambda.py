import os
import json
import logging
import boto3
import urllib.request
import base64
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 로깅 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack & Bedrock 클라이언트 초기화
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
slack_client = WebClient(token=SLACK_BOT_TOKEN)
bedrock_runtime = boto3.client('bedrock-runtime')

def get_claude_response(prompt, image_data):
    try:
        # Bedrock 요청 바디 구성
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data
                            }
                        }, {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "temperature": 0.7
        })
        
        # Bedrock API 호출
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
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
            claude_response = get_claude_response(message, image_base64)
            
            # 슬랙에 메시지 전송
            slack_client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}> {claude_response}"
            )
            
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Success'})
        }
        
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