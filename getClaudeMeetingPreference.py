from datetime import datetime
import json

def get_claude_meeting_preference(bedrock_runtime, prompt, best_time_slots):

    example_output = {
        "best_time": "2023-05-31 12:00",
        "participants": [
            {
                "user_id": "U01ABCDEF",
                "preference": "I'm available at anytime."
            },
            {
                "user_id": "U01GHIJKLM",
                "preference": "I'm available after 2 PM."
            },
            {
                "user_id": "U01GHIJKLM",
                "preference": ""
            }
          ],
      }

    meeting_structure = {
        "best_time": "The best time for the meeting in the format of 'YYYY-MM-DD HH:MM'. (e.g. 2023-05-31 12:00)",
        "participants": [
            {
                "user_id": "The slack user ID of the participant.",
                "preference": "The availability of the participant. (e.g. I'm available at anytime.)"
            }
        ],
    }

    system_prompt = f'''You are a meeting scheduler for a school club. The possible meeting times are provided as a list and the participants might provide their preferences. Analyze the message and extract the following information: the best time for the meeting and the participants' preferences.

Best time: The best time for the meeting in the format of 'YYYY-MM-DD HH:MM'. (e.g. 2023-05-31 12:00) Consider the participants' preferences and choose the time that suits the most participants.

Participants: The list of participants for the meeting. This will be given as slack user IDs. (e.g. U01ABCDEF, U01GHIJKLM) Each participant may provide their availability preference. If the participant does not provide any preference, leave it empty. (empty string: "")

Example output: {json.dumps(example_output)}

Strictly follow the output format

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

        # check whether empty preference is included
        is_empty_exist = False

        for participant in extracted_info['participants']:
            if not participant['preference']:
                is_empty_exist = True
                break                

        # extracted info, is everyone has preference
        return extracted_info, (not is_empty_exist)
        
    except Exception as e:
        print(f"Bedrock API 에러: {str(e)}")
        return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."