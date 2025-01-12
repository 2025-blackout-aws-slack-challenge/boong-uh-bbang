from datetime import datetime
import json

def get_claude_meeting_response(bedrock_runtime, prompt):

    today = datetime.now().strftime('%Y-%m-%d')
    whatday = datetime.now().strftime('%A')

    example_output = {
        "meeting_duration": "1.5",
        "meeting_date_range": "2023-05-31 to 2023-06-01",
        "participants": ["U01ABCDEF", "U01GHIJKLM"],
        "meeting_schedule_finalization_deadline": "2023-05-31"
    }

    meeting_structure = {
        "meeting_duration": "The duration of the meeting in hours or minutes. (e.g. 1 for 1 hour, 1.5 for 1 hour 30 minutes) (integer or float)",
        "meeting_date_range": "The range of dates for the meeting. (e.g. 2023-05-31 to 2023-06-01)",
        "participants": "The list of participants for the meeting. This will be given as slack user IDs. (e.g. U01ABCDEF, U01GHIJKLM)",
        "meeting_schedule_finalization_deadline": "The deadline for finalizing the meeting schedule. This will be given as a date. (e.g. 2023-05-31)",
        "request": "회의 정보를 추출하기 위해 필요한 추가 정보를 요청하세요."
    }

    system_prompt = f'''You are a meeting scheduler for a school club. Users will request you to extract the meeting information from the message. Analyze the message and extract the following information: meeting duration, meeting date range, participants, and meeting schedule finalization deadline. 

Meeting duration: The duration of the meeting in hours or minutes. (e.g. 1 for 1 hour, 1.5 for 1 hour 30 minutes) (integer or float)

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
        print(f"Bedrock API 에러: {str(e)}")
        return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."